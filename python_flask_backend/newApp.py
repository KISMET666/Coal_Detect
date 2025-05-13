import cv2
import threading
import base64
import time
import os
import uuid
import subprocess
import shutil
import json
import numpy as np
from filterpy.kalman import KalmanFilter
import models.user
from scipy.optimize import linear_sum_assignment
from datetime import datetime
from flask import Flask, Response, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename
from ultralytics import YOLO  # 使用Ultralytics官方库
# from socketio import ConnectionRefusedError
# from utils.jwt_utils import decode_token
# 导入认证相关的模块
from api.auth_routes import auth_bp
from config import Config
from utils.jwt_utils import token_required, admin_required
from exts import db

app = Flask(__name__)

CORS(app)

app.config.from_object(Config)

# 初始化数据库
db.init_app(app)

socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=120, ping_interval=25)

# 注册认证相关的路由
app.register_blueprint(auth_bp, url_prefix='/api/auth')

# 默认监控视频保存目录
DEFAULT_SAVE_PATH = Config.DEFAULT_SAVE_PATH

# 加载YOLOv11模型
model = YOLO('best.pt')  # 直接使用Ultralytics的YOLO类加载

# 存储异步任务的字典
processing_tasks = {}
# ===================== 实现SORT追踪算法 ====================
class KalmanBoxTracker(object):
    """
    使用Kalman滤波器实现的单目标追踪器
    """
    count = 0

    def __init__(self, bbox):
        """
        初始化目标追踪器，使用检测框位置
        """
        self.kf = KalmanFilter(dim_x=7, dim_z=4)
        self.kf.F = np.array(
            [[1, 0, 0, 0, 1, 0, 0], [0, 1, 0, 0, 0, 1, 0], [0, 0, 1, 0, 0, 0, 1], [0, 0, 0, 1, 0, 0, 0],
             [0, 0, 0, 0, 1, 0, 0], [0, 0, 0, 0, 0, 1, 0], [0, 0, 0, 0, 0, 0, 1]])
        self.kf.H = np.array(
            [[1, 0, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0, 0], [0, 0, 0, 1, 0, 0, 0]])

        self.kf.R[2:, 2:] *= 10.
        self.kf.P[4:, 4:] *= 1000.
        self.kf.P *= 10.
        self.kf.Q[4:, 4:] *= 0.01

        self.kf.x[:4] = convert_bbox_to_z(bbox)
        self.time_since_update = 0
        self.id = KalmanBoxTracker.count
        KalmanBoxTracker.count += 1
        self.history = []
        self.hits = 0
        self.hit_streak = 0
        self.age = 0
        self.class_name = None
        self.confidence = 0

    def update(self, bbox, class_name=None, confidence=None):
        """
        使用检测框更新位置，重置计数器
        """
        self.time_since_update = 0
        self.history = []
        self.hits += 1
        self.hit_streak += 1
        self.kf.update(convert_bbox_to_z(bbox))
        if class_name is not None:
            self.class_name = class_name
        if confidence is not None:
            self.confidence = confidence

    def predict(self):
        """
        预测下一帧位置
        """
        if ((self.kf.x[6] + self.kf.x[2]) <= 0):
            self.kf.x[6] *= 0.0
        self.kf.predict()
        self.age += 1
        if (self.time_since_update > 0):
            self.hit_streak = 0
        self.time_since_update += 1
        self.history.append(convert_x_to_bbox(self.kf.x))
        return self.history[-1]

    def get_state(self):
        """
        返回当前位置估计
        """
        return convert_x_to_bbox(self.kf.x)


def convert_bbox_to_z(bbox):
    """
    将[x1,y1,x2,y2]格式的边界框转换为[x,y,s,r]格式
    x,y是中心点，s是面积，r是宽高比
    """
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = bbox[0] + w / 2.
    y = bbox[1] + h / 2.
    s = w * h
    r = w / float(h) if h > 0 else 1.0
    return np.array([x, y, s, r]).reshape((4, 1))


def convert_x_to_bbox(x, score=None):
    """
    将[x,y,s,r]格式转换回[x1,y1,x2,y2]格式
    """
    w = np.sqrt(x[2] * x[3])
    h = x[2] / w
    if (score == None):
        return np.array([x[0] - w / 2., x[1] - h / 2., x[0] + w / 2., x[1] + h / 2.]).reshape((1, 4))
    else:
        return np.array([x[0] - w / 2., x[1] - h / 2., x[0] + w / 2., x[1] + h / 2., score]).reshape((1, 5))


def associate_detections_to_trackers(detections, trackers, iou_threshold=0.3):
    """
    使用匈牙利算法将检测结果与现有追踪器关联
    """
    if len(trackers) == 0:
        return np.empty((0, 2), dtype=int), np.arange(len(detections)), np.empty((0, 5), dtype=int)

    iou_matrix = np.zeros((len(detections), len(trackers)), dtype=np.float32)

    for d, det in enumerate(detections):
        for t, trk in enumerate(trackers):
            iou_matrix[d, t] = calculate_iou(det, trk)

    # 使用匈牙利算法进行关联
    matched_indices = np.array(linear_sum_assignment(-iou_matrix)).T

    # 未匹配的检测结果
    unmatched_detections = []
    for d, det in enumerate(detections):
        if d not in matched_indices[:, 0]:
            unmatched_detections.append(d)

    # 未匹配的追踪器
    unmatched_trackers = []
    for t, trk in enumerate(trackers):
        if t not in matched_indices[:, 1]:
            unmatched_trackers.append(t)

    # 过滤掉低IOU的匹配
    matches = []
    for m in matched_indices:
        if iou_matrix[m[0], m[1]] < iou_threshold:
            unmatched_detections.append(m[0])
            unmatched_trackers.append(m[1])
        else:
            matches.append(m.reshape(1, 2))

    if len(matches) == 0:
        matches = np.empty((0, 2), dtype=int)
    else:
        matches = np.concatenate(matches, axis=0)

    return matches, np.array(unmatched_detections), np.array(unmatched_trackers)


def calculate_iou(box1, box2):
    """
    计算两个框的交并比(IOU)
    """
    # 获取交集区域的坐标
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    # 计算交集面积
    intersection = max(0, x2 - x1) * max(0, y2 - y1)

    # 计算两个框的面积
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])

    # 计算并集面积
    union = box1_area + box2_area - intersection

    # 防止除以0
    if union == 0:
        return 0

    return intersection / union


class Sort(object):
    """
    SORT多目标追踪算法
    """

    def __init__(self, max_age=10, min_hits=3, iou_threshold=0.3):
        """
        参数:
            max_age - 连续帧未关联时删除追踪器的最大帧数
            min_hits - 确认目标存在的最小帧数
            iou_threshold - IOU匹配门限
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.trackers = []
        self.frame_count = 0
        self.unique_ids = set()  # 用于记录唯一煤块ID

    def update(self, dets, class_names=None, confidences=None):
        """
        更新追踪器状态
        参数:
            dets - numpy数组格式 [[x1,y1,x2,y2,score], ...]
        返回:
            带有唯一ID的追踪结果
        """
        self.frame_count += 1

        # 获取当前追踪器预测的位置
        trks = np.zeros((len(self.trackers), 5))
        to_del = []
        ret = []
        for t, trk in enumerate(trks):
            pos = self.trackers[t].predict()[0]
            trk[:] = [pos[0], pos[1], pos[2], pos[3], 0]
            if np.any(np.isnan(pos)):
                to_del.append(t)

        # 删除失效的追踪器
        trks = np.ma.compress_rows(np.ma.masked_invalid(trks))
        for t in reversed(to_del):
            self.trackers.pop(t)

        # 将当前帧检测关联到已有追踪
        matched, unmatched_dets, unmatched_trks = associate_detections_to_trackers(dets, trks, self.iou_threshold)

        # 更新已匹配的追踪器
        for m in matched:
            if class_names is not None and confidences is not None:
                self.trackers[m[1]].update(dets[m[0]], class_names[m[0]], confidences[m[0]])
            else:
                self.trackers[m[1]].update(dets[m[0]])

        # 为未匹配的检测创建新的追踪器
        for i in unmatched_dets:
            if class_names is not None and confidences is not None:
                trk = KalmanBoxTracker(dets[i])
                trk.class_name = class_names[i]
                trk.confidence = confidences[i]
            else:
                trk = KalmanBoxTracker(dets[i])
            self.trackers.append(trk)

        # 返回确认的追踪结果
        i = len(self.trackers)
        for trk in reversed(self.trackers):
            d = trk.get_state()[0]

            # 只返回确认的追踪结果 (至少连续min_hits帧被追踪)
            if trk.time_since_update < 1 and (trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits):
                ret.append(np.concatenate((d, [trk.id + 1])).reshape(1, -1))  # +1 因为0是保留ID

                # 记录唯一ID
                self.unique_ids.add(trk.id + 1)

            i -= 1

            # 移除已经很久未更新的追踪器
            if trk.time_since_update > self.max_age:
                self.trackers.pop(i)

        if len(ret) > 0:
            return np.concatenate(ret), len(self.unique_ids)
        return np.empty((0, 5)), len(self.unique_ids)
# ===================== 摄像头流处理部分 =====================

# 模拟9个摄像头（只有第一个使用真实摄像头）
camera_indices = [0, -1, -1, -1, -1, -1, -1, -1, -1]  # 9个摄像头，只有第一个连接


class Camera:
    def __init__(self, index):
        self.index = index
        if index >= 0:
            self.cap = cv2.VideoCapture(index)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 960)
        else:
            self.cap = None
        self.lock = threading.Lock()
        self.clients = 0
        self.detecting = False
        self.detection_thread = None
        self.video_writer = None
        self.video_start_time = None
        self.current_video_path = None
        self.current_results_path = None
        self.segment_duration = 15 * 60  # 15分钟视频片段
        self.detection_results = []
        self.save_path = DEFAULT_SAVE_PATH
        # 添加追踪器
        self.tracker = Sort(max_age=20, min_hits=2, iou_threshold=0.3)
        self.unique_coal_count = 0  # 唯一煤块计数
        self.frame_index = 0  # 帧计数
        self.frame_count = 0  # 确保添加这一行

    # 捕获视频流生成帧
    def get_frame(self):
        if self.cap is None:
            return None

        with self.lock:
            success, frame = self.cap.read()
            if not success:
                return None

            # 如果正在检测，保存帧到视频中
            if self.detecting and frame is not None:
                self.handle_detection(frame)

            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return buffer.tobytes()

    # 处理检测并保存视频
    def handle_detection(self, frame):
        """处理检测并保存视频"""
        # 确保视频保存目录存在
        daily_folder = os.path.join(self.save_path, datetime.now().strftime('%Y-%m-%d'))
        os.makedirs(daily_folder, exist_ok=True)

        current_time = time.time()
        self.frame_index += 1
        # 创建或切换视频片段
        if (self.video_writer is None or
                self.video_start_time is None or
                current_time - self.video_start_time >= self.segment_duration):

            # 关闭现有视频写入器
            if self.video_writer is not None:
                self.video_writer.release()

                # 通知前端视频已保存
                if self.current_video_path:
                    socketio.emit('video_saved', {
                        'camera_id': self.index,
                        'file_path': self.current_video_path,
                        'timestamp': current_time
                    })

            # 创建新的视频片段
            timestamp = datetime.now().strftime('%H-%M-%S')
            video_filename = f'cam{self.index}_seg_{timestamp}.mp4'
            self.current_video_path = os.path.join(daily_folder, video_filename)

            # 获取视频参数
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            # 如果帧率异常，设置为合理的默认值
            if fps <= 0 or fps > 60:  # 通常摄像头帧率不超过60fps
                fps = 20.0  # 使用合理的默认帧率
                print(f"摄像头 {self.index} 帧率获取失败，使用默认值 {fps}fps")
            else:
                print(f"摄像头 {self.index} 帧率: {fps}fps")
            # 尝试使用更兼容的编码器
            try:
                # 尝试使用 H.264 编码
                fourcc = cv2.VideoWriter.fourcc(*'avc1')  # 或者尝试 'H264'
                self.video_writer = cv2.VideoWriter(
                    self.current_video_path, fourcc, fps, (width, height)
                )

                # 如果无法创建，回退到其他编码器
                if not self.video_writer.isOpened():
                    fourcc = cv2.VideoWriter.fourcc(*'XVID')  # 尝试 XVID 编码
                    self.video_writer = cv2.VideoWriter(
                        self.current_video_path, fourcc, fps, (width, height)
                    )
            except:
                # 最后回退到 mp4v
                fourcc = cv2.VideoWriter.fourcc(*'mp4v')
                self.video_writer = cv2.VideoWriter(
                    self.current_video_path, fourcc, fps, (width, height)
                )
            self.video_start_time = current_time
            self.frame_count = 0  # 添加帧计数器

            # # 计算相对时间戳（秒）- 从视频开始的相对时间
            # relative_timestamp = current_time - self.video_start_time

            # 创建对应的检测结果文件
            results_filename = f'cam{self.index}_seg_{timestamp}.json'
            self.current_results_path = os.path.join(daily_folder, results_filename)
            self.detection_results = []

        # 增加帧计数
        self.frame_count += 1
        # 计算相对时间戳（秒）- 基于帧计数和帧率
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        if fps > 0 and self.frame_count > 0:
            # 基于帧数和帧率计算更精确的相对时间
            relative_time = self.frame_count / fps
        else:
            # 如果无法通过帧率计算，则使用真实时间差
            relative_time = current_time - self.video_start_time
        # 执行对象检测
        results = model(frame, verbose=False)

        # 将检测结果转换为SORT兼容的格式
        detections = []
        class_names = []
        confidences = []

        for box in results[0].boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            confidence = float(box.conf)
            class_name = model.names[int(box.cls)]

            # 只追踪置信度超过阈值的目标
            if confidence > 0.3:  # 可调整的阈值
                detections.append([x1, y1, x2, y2])
                class_names.append(class_name)
                confidences.append(confidence)

        # 更新追踪器
        if detections:
            detections_array = np.array(detections)
            tracked_objects, unique_count = self.tracker.update(detections_array, class_names, confidences)
            self.unique_coal_count = unique_count  # 更新唯一煤块计数
        else:
            tracked_objects = np.empty((0, 5))

        # 记录跟踪结果
        frame_detections = []
        for tracked_obj in tracked_objects:
            x1, y1, x2, y2, track_id = tracked_obj

            # 获取当前追踪ID对应的追踪器
            tracker_idx = None
            for i, trk in enumerate(self.tracker.trackers):
                if trk.id + 1 == track_id:  # +1 是因为我们在返回时加了1
                    tracker_idx = i
                    break

            if tracker_idx is not None:
                trk = self.tracker.trackers[tracker_idx]
                detection = {
                    'class': trk.class_name,
                    'confidence': trk.confidence,
                    'bbox': [x1, y1, x2, y2],
                    'track_id': int(track_id),
                    'abs_timestamp': current_time,  # 保留绝对时间戳
                    'rel_timestamp': relative_time,  # 添加相对时间戳
                    'frame_number': self.frame_count  # 添加帧号
                }
                frame_detections.append(detection)
                self.detection_results.append(detection)

        # 在帧上绘制检测结果和追踪ID
        annotated_frame = frame.copy()

        for det in frame_detections:
            x1, y1, x2, y2 = map(int, det['bbox'])
            track_id = det['track_id']
            class_name = det['class']
            confidence = det['confidence']

            # 绘制边界框
            color = (0, 255, 0) if class_name == 'coal' else (0, 0, 255)  # 煤是绿色，岩石是红色
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)

            # 绘制追踪ID和类别信息
            label = f"ID:{track_id} {class_name} {confidence:.2f}"
            cv2.putText(annotated_frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # 在帧上添加统计信息
        info_text = f"唯一煤块数量: {self.unique_coal_count} | 当前帧: {self.frame_index}"
        cv2.putText(annotated_frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # 写入帧到视频文件
        if self.video_writer is not None:
            self.video_writer.write(annotated_frame)

        # 保存检测结果到JSON文件
        if self.detection_results:
            # 分离原始检测结果和唯一煤块统计
            unique_coal_blocks = {}

            # 根据track_id整理唯一煤块
            for detection in self.detection_results:
                track_id = detection['track_id']
                if track_id not in unique_coal_blocks:
                    unique_coal_blocks[track_id] = detection.copy()
                else:
                    # 更新已存在煤块的最后出现信息
                    unique_coal_blocks[track_id]['last_timestamp'] = detection['abs_timestamp']
                    unique_coal_blocks[track_id]['last_rel_timestamp'] = detection['rel_timestamp']
                    unique_coal_blocks[track_id]['last_frame'] = detection['frame_number']
                    # 如果需要更新其他信息，比如置信度等
                    if detection['confidence'] > unique_coal_blocks[track_id]['confidence']:
                        unique_coal_blocks[track_id]['confidence'] = detection['confidence']
                        unique_coal_blocks[track_id]['bbox'] = detection['bbox']

            # 获取唯一煤块列表
            unique_detections = list(unique_coal_blocks.values())

            # 添加视频元数据信息
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0 or fps > 60:
                fps = 20.0  # 使用默认值
            video_metadata = {
                'start_time': self.video_start_time,
                'current_time': current_time,
                'duration': current_time - self.video_start_time,
                'frame_count': self.frame_count,
                'fps': fps
            }
            # 保存JSON结果
            with open(self.current_results_path, 'w') as f:
                json.dump({
                    'camera_id': self.index,
                    'video_path': self.current_video_path,
                    'video_metadata': video_metadata,  # 新增：视频元数据
                    'detections': self.detection_results,  # 原始检测结果
                    'unique_detections': unique_detections,  # 唯一煤块结果
                    'unique_count': len(unique_detections)  # 唯一煤块数量
                }, f, indent=2)

        # 发送实时检测结果给前端
        if frame_detections:
            normalized_detections = []
            height, width = frame.shape[:2]

            for detection in frame_detections:
                # 转换坐标为百分比以适应不同尺寸的显示
                x1, y1, x2, y2 = detection['bbox']
                normalized_detections.append({
                    'class': detection['class'],
                    'confidence': detection['confidence'],
                    'track_id': detection['track_id'],  # 添加追踪ID
                    'rel_timestamp': detection['rel_timestamp'],  # 添加相对时间戳
                    'frame_number': detection['frame_number'],  # 添加帧号
                    'bbox': [
                        x1 / width * 100,  # 转为百分比
                        y1 / height * 100,
                        x2 / width * 100,
                        y2 / height * 100
                    ]
                })

            socketio.emit(f'detection_result_{self.index}', {
                'detections': normalized_detections,
                'count': self.unique_coal_count,  # 发送唯一煤块数量
                'current_count': len(normalized_detections),  # 当前帧检测数量
                'frame_count': self.frame_count,  # 当前帧计数
                'rel_time': relative_time  # 相对时间
            })

    # 开始检测和录制
    def start_detection(self, save_path=None, sensitivity=0.5):
        """开始检测和录制"""
        if save_path:
            self.save_path = save_path

        # 确保保存目录存在
        os.makedirs(self.save_path, exist_ok=True)

        # 设置模型置信度阈值
        model.conf = sensitivity

        self.detecting = True
        return True

    # 停止检测和录制
    def stop_detection(self):
        """停止检测和录制"""
        self.detecting = False

        # 关闭视频写入器
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None

            # 通知前端最后一个视频已保存
            if self.current_video_path:
                socketio.emit('video_saved', {
                    'camera_id': self.index,
                    'file_path': self.current_video_path,
                    'timestamp': time.time()
                })

        return True


# 初始化9个摄像头实例
cameras = [Camera(i) for i in camera_indices]


def generate_frames(camera_id):
    """生成MJPEG流的帧数据"""
    while True:
        frame = cameras[camera_id].get_frame()
        if frame is None:
            break
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


def emit_frames(socketio, camera_id):
    """通过WebSocket发送帧数据"""
    while True:
        frame = cameras[camera_id].get_frame()
        if frame is None:
            break
        socketio.emit(f'video_frame_{camera_id}', {
            'frame': base64.b64encode(frame).decode('utf-8'),
            'timestamp': time.time()
        })
        socketio.sleep(0.05)  # 控制帧率(约20fps)


def open_folder(path):
    """打开指定文件夹"""
    if os.path.exists(path):
        if os.name == 'nt':  # Windows
            os.startfile(path)
        elif os.name == 'posix':  # macOS和Linux
            if shutil.which('xdg-open'):  # Linux
                subprocess.call(['xdg-open', path])
            elif shutil.which('open'):  # macOS
                subprocess.call(['open', path])
        return True
    return False


# ===================== 图像/视频检测部分 =====================

def process_image(image_path):
    """处理图片检测"""
    results = model(image_path)  # 直接预测
    rendered_img = results[0].plot()  # 获取渲染后的图像

    # 保存结果图片
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], f'result_{int(time.time())}.jpg')
    print(f"尝试保存结果图片到: {output_path}")  # 调试输出
    success = cv2.imwrite(output_path, rendered_img)
    if not success:
        print("错误: 图片保存失败!")
        return None, []

    print(f"图片保存成功，大小: {os.path.getsize(output_path)} 字节")  # 调试输出
    # 获取检测结果数据
    detections = []
    for box in results[0].boxes:
        detections.append({
            'class': model.names[int(box.cls)],
            'confidence': float(box.conf),
            'bbox': box.xyxy[0].tolist()
        })

    return output_path, detections


def process_video(video_path, task_id=None):
    """处理视频检测，支持进度更新"""
    print(f"开始处理视频: {video_path}")
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print("错误: 无法打开视频文件")
            return None, []

        # 获取视频信息
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"视频信息: {width}x{height}, {fps}FPS, 总帧数: {total_frames}")

        # 创建输出视频
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], f'result_{int(time.time())}.mp4')

        # 创建追踪器
        tracker = Sort(max_age=20, min_hits=2, iou_threshold=0.3)

        # 用于跟踪所有唯一煤块
        all_unique_tracks = {}  # 用ID作为键存储所有唯一煤块

        # 尝试多种编码器
        codecs = [
            ('H264', 'H264'),
            ('avc1', 'avc1'),
            ('mp4v', 'mp4v')
        ]

        out = None
        for codec_name, codec_code in codecs:
            try:
                fourcc = cv2.VideoWriter.fourcc(*codec_code)
                out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
                if out.isOpened():
                    print(f"使用 {codec_name} 编码器成功")
                    break
            except Exception as e:
                print(f"尝试 {codec_name} 编码器失败: {str(e)}")
                if out:
                    out.release()
                out = None

        if not out or not out.isOpened():
            raise Exception("无法创建输出视频，所有编码器都失败")

        # 处理视频并检测
        frame_count = 0
        last_progress_report = time.time()

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # 使用YOLOv11检测
            results = model(frame, verbose=False)


            # 准备SORT输入
            det_boxes = []
            confidences = []

            for box in results[0].boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                confidence = float(box.conf)

                if confidence > 0.3:  # 可调整阈值
                    det_boxes.append([x1, y1, x2, y2])
                    confidences.append(confidence)

            # 更新追踪器
            tracked_objects = np.empty((0, 5))
            if det_boxes:
                det_boxes_array = np.array(det_boxes)
                class_names = ["Coal"] * len(det_boxes)
                tracked_objects,_ = tracker.update(det_boxes_array, class_names, confidences)


            # 绘制结果到帧上
            annotated_frame = frame.copy()

            for tracked_obj in tracked_objects:
                x1, y1, x2, y2, track_id = tracked_obj

                # 查找对应的追踪器获取类别和置信度
                tracker_idx = None
                for i, trk in enumerate(tracker.trackers):
                    if trk.id + 1 == track_id:
                        tracker_idx = i
                        break

                if tracker_idx is not None:
                    trk = tracker.trackers[tracker_idx]
                    class_name = "Coal"
                    confidence = trk.confidence

                    # 保存或更新唯一煤块信息
                    track_id_int = int(track_id)
                    if track_id_int not in all_unique_tracks:
                        # 首次出现，添加到字典
                        all_unique_tracks[track_id_int] = {
                            'class': class_name,
                            'confidence': confidence,
                            'bbox': [x1, y1, x2, y2],
                            'track_id': track_id_int,
                            'first_frame': frame_count,
                            'last_frame': frame_count
                        }
                    else:
                        # 已存在，更新最后出现的帧
                        all_unique_tracks[track_id_int]['last_frame'] = frame_count
                        # 更新为最佳的检测框和置信度
                        if confidence > all_unique_tracks[track_id_int]['confidence']:
                            all_unique_tracks[track_id_int]['confidence'] = confidence
                            all_unique_tracks[track_id_int]['bbox'] = [x1, y1, x2, y2]

                    # 绘制边界框和标签
                    color = (0, 255, 0) if class_name == 'coal' else (0, 0, 255)
                    cv2.rectangle(annotated_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                    label = f"ID:{int(track_id)} {class_name} {confidence:.2f}"
                    cv2.putText(annotated_frame, label, (int(x1), int(y1) - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # 添加统计信息
            info_text = f"唯一煤块数量: {len(all_unique_tracks)} | 帧: {frame_count}/{total_frames}"
            cv2.putText(annotated_frame, info_text, (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            # 写入帧
            out.write(annotated_frame)

            frame_count += 1

            # 每秒报告一次进度
            if time.time() - last_progress_report > 1.0:
                progress = (frame_count / total_frames) * 100 if total_frames > 0 else 0
                print(f"视频处理进度: {progress:.1f}% ({frame_count}/{total_frames})")
                last_progress_report = time.time()

                # 更新任务进度
                if task_id and task_id in processing_tasks:
                    processing_tasks[task_id]['progress'] = progress
                    socketio.emit('video_progress', {
                        'task_id': task_id,
                        'progress': progress
                    })
        # 整理所有唯一煤块信息为列表
        final_detections = list(all_unique_tracks.values())
        # 按ID排序
        final_detections.sort(key=lambda x: x['track_id'])
        # 创建数据汇总
        summary = {
            'total_count': len(final_detections),
            'total_frames': frame_count,
            'video_duration': frame_count / fps if fps > 0 else 0,
            'average_confidence': sum(d['confidence'] for d in final_detections) / len(
                final_detections) if final_detections else 0,
            'size_distribution': {
                'small': 0,
                'medium': 0,
                'large': 0
            },
            'frame_distribution': {}
        }

        # 计算煤块大小分布
        for det in final_detections:
            bbox = det['bbox']
            area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])

            if area < 5000:  # 可根据实际情况调整阈值
                summary['size_distribution']['small'] += 1
            elif area < 20000:
                summary['size_distribution']['medium'] += 1
            else:
                summary['size_distribution']['large'] += 1

        # 计算煤块在视频中的分布
        if frame_count > 0:
            segment_count = 5
            segment_size = frame_count // segment_count

            for i in range(segment_count):
                start_frame = i * segment_size
                end_frame = (i + 1) * segment_size if i < segment_count - 1 else frame_count
                segment_name = f"{start_frame}-{end_frame}"

                # 计算在此时间段首次出现的煤块数量
                count = sum(1 for d in final_detections if start_frame <= d['first_frame'] < end_frame)
                summary['frame_distribution'][segment_name] = count

        # 清理资源
        cap.release()
        out.release()

        # 验证输出文件
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise Exception("视频文件创建失败或为空")

        print(f"视频处理完成: {output_path}, 大小: {os.path.getsize(output_path)} 字节")
        print(f"共检测到 {len(final_detections)} 个唯一煤块")

        return output_path,final_detections, summary

    except Exception as e:
        print(f"视频处理异常: {str(e)}")
        # 确保资源被释放
        if 'cap' in locals() and cap:
            cap.release()
        if 'out' in locals() and out:
            out.release()
        raise e


def background_process_video(video_path, task_id):
    """后台处理视频的任务"""
    try:
        # 更新任务状态为处理中
        processing_tasks[task_id]['status'] = 'processing'
        processing_tasks[task_id]['progress'] = 0

        # 处理视频
        result_path, detections,summary = process_video(video_path, task_id)

        # 更新任务状态为已完成
        processing_tasks[task_id] = {
            'status': 'completed',
            'result_path': result_path,
            'detections': detections,
            'unique_count': len(detections),  # 唯一煤块数
            'summary': summary,
            'progress': 100
        }

        # 向所有客户端广播任务完成事件
        # socketio.emit('task_completed', {
        #     'task_id': task_id,
        #     'result_url': f'/results/{os.path.basename(result_path)}'
        # })

    except Exception as e:
        print(f"视频处理失败: {str(e)}")
        # 更新任务状态为失败
        processing_tasks[task_id] = {
            'status': 'failed',
            'error': str(e)
        }

        # 向所有客户端广播任务失败事件
        socketio.emit('task_failed', {
            'task_id': task_id,
            'error': str(e)
        })


def upgrade_detection_files():
    """升级现有的检测结果文件，添加唯一煤块数据"""
    print("开始升级检测文件...")

    # 遍历所有日期文件夹
    for date_folder in os.listdir(DEFAULT_SAVE_PATH):
        date_path = os.path.join(DEFAULT_SAVE_PATH, date_folder)
        if not os.path.isdir(date_path):
            continue

        # 查找所有JSON文件
        json_files = [f for f in os.listdir(date_path) if f.endswith('.json')]

        for json_file in json_files:
            json_path = os.path.join(date_path, json_file)
            print(f"处理文件: {json_path}")

            try:
                # 读取原始数据
                with open(json_path, 'r') as f:
                    data = json.load(f)

                # 跳过已经包含唯一煤块数据的文件
                if 'unique_detections' in data:
                    print("  已包含唯一煤块数据，跳过")
                    continue

                # 处理检测结果
                detections = data.get('detections', [])
                unique_blocks = {}

                # 根据track_id或位置去重
                for det in detections:
                    if 'track_id' in det:
                        # 使用track_id
                        track_id = det['track_id']
                        if track_id not in unique_blocks:
                            unique_blocks[track_id] = det.copy()
                        # 如果需要更新其他信息，比如时间戳或置信度
                        if 'timestamp' in det and ('timestamp' not in unique_blocks[track_id] or det['timestamp'] >
                                                   unique_blocks[track_id]['timestamp']):
                            unique_blocks[track_id]['last_appearance'] = det['timestamp']
                    else:
                        # 使用位置作为近似标识
                        bbox = det.get('bbox', [0, 0, 0, 0])
                        pos_key = f"{int(bbox[0])}-{int(bbox[1])}"
                        if pos_key not in unique_blocks:
                            unique_blocks[pos_key] = det.copy()

                # 获取唯一煤块列表
                unique_detections = list(unique_blocks.values())

                # 更新数据
                data['unique_detections'] = unique_detections
                data['unique_count'] = len(unique_detections)

                # 保存更新后的数据
                with open(json_path, 'w') as f:
                    json.dump(data, f, indent=2)

                print(f"  更新完成: {len(detections)} 个检测 -> {len(unique_detections)} 个唯一煤块")

            except Exception as e:
                print(f"  处理失败: {str(e)}")

    print("检测文件升级完成")
# ===================== 路由和WebSocket事件 =====================

# 视频流路由
@app.route('/api/video_feed/<int:camera_id>')
def video_feed(camera_id):
    """提供MJPEG流的路由"""
    if 0 <= camera_id < len(cameras):
        if cameras[camera_id].cap is not None:
            return Response(generate_frames(camera_id),
                            mimetype='multipart/x-mixed-replace; boundary=frame')
        else:
            return "Camera not connected", 404
    return "Invalid camera ID", 404


# 检测API路由
@app.route('/api/detect/image', methods=['POST'])
@token_required
def detect_image(current_user):
    """图片检测接口"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        result_path, detections = process_image(filepath)
        return jsonify({
            'result_url': f'/results/{os.path.basename(result_path)}',
            'detections': detections
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/detect/video', methods=['POST'])
@token_required
def detect_video(current_user):
    """视频检测接口 - 异步版本"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # 创建唯一任务ID
    task_id = str(uuid.uuid4())
    processing_tasks[task_id] = {
        'status': 'initialized',
        'progress': 0,
        'created_at': time.time(),
        'user_id': current_user['sub']  # 记录哪个用户创建的任务
    }

    # 启动后台任务
    thread = threading.Thread(target=background_process_video, args=(filepath, task_id))
    thread.daemon = True
    thread.start()

    # 立即返回任务ID
    return jsonify({
        'task_id': task_id,
        'status': 'processing',
        'progress': 0
    })


@app.route('/api/task/<task_id>', methods=['GET'])
@token_required
def get_task_status(current_user, task_id):
    """获取任务状态"""
    if task_id not in processing_tasks:
        return jsonify({'error': 'Task not found'}), 404

    task = processing_tasks[task_id]

    # 检查该任务是否属于当前用户，管理员除外
    if current_user['role'] != 'admin' and task.get('user_id') != current_user['sub']:
        return jsonify({'error': 'Unauthorized access to this task'}), 403

    if task['status'] == 'completed':
        # 默认只返回汇总信息和前10个示例
        include_details = request.args.get('details', 'false').lower() == 'true'

        response_data = {
            'status': 'completed',
            'result_url': f'/results/{os.path.basename(task["result_path"])}',
            'unique_count': task.get('unique_count', 0),
            'summary': task.get('summary', {})
        }

        # 只有当客户端请求时才返回详细数据
        if include_details:
            response_data['detections'] = task['detections']
        else:
            # 只返回前10个作为示例
            response_data['detections'] = task['detections'][:10] if len(task['detections']) > 10 else task[
                'detections']
            response_data['has_more_detections'] = len(task['detections']) > 10

        return jsonify(response_data)

    elif task['status'] == 'failed':
        # 如果任务失败，返回错误信息
        return jsonify({
            'status': 'failed',
            'error': task.get('error', 'Unknown error')
        }), 500
    else:
        # 如果任务仍在处理，返回进度信息
        return jsonify({
            'status': task['status'],
            'progress': task.get('progress', 0)
        })


@app.route('/api/task/<task_id>/detections', methods=['GET'])
@token_required
def get_task_detections(current_user, task_id):
    """获取任务的完整检测结果"""
    if task_id not in processing_tasks:
        return jsonify({'error': 'Task not found'}), 404

    task = processing_tasks[task_id]

    # 检查该任务是否属于当前用户，管理员除外
    if current_user['role'] != 'admin' and task.get('user_id') != current_user['sub']:
        return jsonify({'error': 'Unauthorized access to this task'}), 403

    if task['status'] != 'completed':
        return jsonify({'error': 'Task not completed yet'}), 400

    # 支持分页
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))

    detections = task.get('detections', [])
    total_count = len(detections)

    # 计算分页
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_count)

    page_detections = detections[start_idx:end_idx]

    return jsonify({
        'detections': page_detections,
        'page': page,
        'page_size': page_size,
        'total_count': total_count,
        'total_pages': (total_count + page_size - 1) // page_size
    })

@app.route('/results/<filename>')
def get_result(filename):
    """获取处理结果文件"""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(filepath):
        print(f"文件未找到: {filepath}")
        return "File not found", 404

    print(f"提供文件: {filepath}, 大小: {os.path.getsize(filepath)} 字节")

    # 使用流式响应
    def generate():
        with open(filepath, 'rb') as video_file:
            chunk_size = 1024 * 1024  # 1MB 块大小
            while True:
                chunk = video_file.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    # 根据文件扩展名设置正确的MIME类型
    if filename.endswith('.mp4'):
        response = Response(generate(), mimetype='video/mp4')
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Connection'] = 'keep-alive'
        return response
    elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
        mimetype = 'image/jpeg'
        response = send_from_directory(
            app.config['UPLOAD_FOLDER'],
            filename,
            mimetype=mimetype
        )
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    else:
        mimetype = 'application/octet-stream'
        response = send_from_directory(
            app.config['UPLOAD_FOLDER'],
            filename,
            mimetype=mimetype
        )
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response


@app.route('/diagnose/<filename>')
@token_required
def diagnose_file(current_user, filename):
    """诊断文件端点"""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not os.path.exists(filepath):
        return jsonify({
            'exists': False,
            'error': 'File not found'
        })

    file_info = {
        'exists': True,
        'size': os.path.getsize(filepath),
        'path': filepath,
        'url': f'/results/{filename}',
        'content_type': 'video/mp4' if filename.endswith('.mp4') else 'unknown'
    }

    # 尝试读取文件的前100字节来验证
    try:
        with open(filepath, 'rb') as f:
            file_info['header'] = f.read(100).hex()
    except Exception as e:
        file_info['read_error'] = str(e)

    return jsonify(file_info)


# WebSocket事件
@socketio.on('connect')
def handle_connect():
    print('Client connected')


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


@socketio.on('start_stream')
def handle_start_stream(data):
    """客户端请求开始流"""
    camera_id = data.get('camera_id', 0)
    if 0 <= camera_id < len(cameras):
        cameras[camera_id].clients += 1
        if cameras[camera_id].clients == 1:
            socketio.start_background_task(emit_frames, socketio, camera_id)


@socketio.on('stop_stream')
def handle_stop_stream(data):
    """客户端请求停止流"""
    camera_id = data.get('camera_id', 0)
    if 0 <= camera_id < len(cameras):
        cameras[camera_id].clients -= 1


@socketio.on('start_detection')
def handle_start_detection(data):
    """客户端请求开始检测"""
    camera_id = data.get('camera_id', 0)
    sensitivity = data.get('sensitivity', 0.5)
    save_path = data.get('save_path', DEFAULT_SAVE_PATH)

    try:
        if 0 <= camera_id < len(cameras) and cameras[camera_id].cap is not None:
            success = cameras[camera_id].start_detection(save_path, sensitivity)
            return {'success': success}
        else:
            return {'success': False, 'error': '摄像头未连接'}
    except Exception as e:
        print(f"开始检测错误: {str(e)}")
        return {'success': False, 'error': str(e)}


@socketio.on('stop_detection')
def handle_stop_detection(data):
    """客户端请求停止检测"""
    camera_id = data.get('camera_id', 0)

    try:
        if 0 <= camera_id < len(cameras):
            success = cameras[camera_id].stop_detection()
            return {'success': success}
        else:
            return {'success': False, 'error': '无效的摄像头ID'}
    except Exception as e:
        print(f"停止检测错误: {str(e)}")
        return {'success': False, 'error': str(e)}


@socketio.on('open_save_folder')
def handle_open_save_folder(data):
    """打开保存文件夹"""
    path = data.get('path', DEFAULT_SAVE_PATH)
    success = open_folder(path)
    return {'success': success}


# 清理过期任务的后台线程
def cleanup_tasks():
    """定期清理完成或失败超过1小时的任务"""
    while True:
        time.sleep(3600)  # 每小时运行一次
        current_time = time.time()
        task_ids_to_remove = []

        for task_id, task in processing_tasks.items():
            # 如果任务已完成或失败，且超过1小时
            if (task['status'] in ['completed', 'failed'] and
                    current_time - task.get('created_at', current_time) > 3600):
                task_ids_to_remove.append(task_id)

        # 移除过期任务
        for task_id in task_ids_to_remove:
            del processing_tasks[task_id]

        if task_ids_to_remove:
            print(f"已清理 {len(task_ids_to_remove)} 个过期任务")


# 添加新API路由，用于获取检测历史和视频列表
@app.route('/api/surveillance/history', methods=['GET'])
@token_required
def get_surveillance_history(current_user):
    """获取监控历史记录"""
    try:
        if not os.path.exists(DEFAULT_SAVE_PATH):
            return jsonify([])

        # 获取日期文件夹
        date_folders = [f for f in os.listdir(DEFAULT_SAVE_PATH)
                        if os.path.isdir(os.path.join(DEFAULT_SAVE_PATH, f))]
        date_folders.sort(reverse=True)  # 最新日期在前

        result = []

        for date_folder in date_folders:
            folder_path = os.path.join(DEFAULT_SAVE_PATH, date_folder)

            # 获取视频文件
            video_files = [f for f in os.listdir(folder_path)
                           if f.endswith('.mp4')]

            # 获取检测结果文件
            json_files = [f for f in os.listdir(folder_path)
                          if f.endswith('.json')]

            date_entry = {
                'date': date_folder,
                'videos': [],
                'detection_count': 0
            }

            # 处理每个视频及其对应的检测结果
            for video in video_files:
                # 查找对应的检测结果
                base_name = video.rsplit('.', 1)[0]
                json_file = f"{base_name}.json"

                video_entry = {
                    'filename': video,
                    'path': os.path.join(folder_path, video),
                    'url': f'/surveillance/{date_folder}/{video}',
                    'size': os.path.getsize(os.path.join(folder_path, video)),
                    'time': os.path.getctime(os.path.join(folder_path, video)),
                    'has_detections': json_file in json_files
                }

                # 如果有检测结果，加载并统计
                if json_file in json_files:
                    try:
                        with open(os.path.join(folder_path, json_file), 'r') as f:
                            detection_data = json.load(f)
                            # 优先使用唯一煤块数量
                            if 'unique_count' in detection_data:
                                detection_count = detection_data['unique_count']
                            else:
                                detection_count = len(detection_data.get('detections', []))

                            video_entry['detection_count'] = detection_count
                            date_entry['detection_count'] += detection_count
                    except Exception as e:
                        print(f"读取检测结果错误 {json_file}: {str(e)}")
                        video_entry['detection_count'] = 0

                date_entry['videos'].append(video_entry)

            # 按时间排序视频
            date_entry['videos'].sort(key=lambda x: x['time'], reverse=True)
            result.append(date_entry)

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/surveillance/<date>/<filename>')
@token_required
def get_surveillance_video(current_user, date, filename):
    """获取监控视频文件"""
    filepath = os.path.join(DEFAULT_SAVE_PATH, date, filename)
    print(f"请求监控视频文件: {filepath}")
    print(f"文件是否存在: {os.path.exists(filepath)}")

    if not os.path.exists(filepath):
        return "File not found", 404

    print(f"提供监控视频文件: {filepath}, 大小: {os.path.getsize(filepath)} 字节")
    print(f"视频所在目录: {os.path.join(DEFAULT_SAVE_PATH, date)}")

    try:
        # 使用流式响应来传输大文件
        def generate():
            with open(filepath, 'rb') as video_file:
                chunk_size = 1024 * 1024  # 1MB 块大小
                while True:
                    chunk = video_file.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

        # 创建流式响应
        response = Response(generate(), mimetype='video/mp4')

        # 添加必要的响应头
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Connection'] = 'keep-alive'

        return response
    except Exception as e:
        print(f"视频传输错误: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/surveillance/detection/<date>/<filename>')
@token_required
def get_detection_results(current_user, date, filename):
    """获取检测结果数据"""
    # 去掉扩展名并加上.json
    base_filename = filename.rsplit('.', 1)[0]
    json_filename = f"{base_filename}.json"

    filepath = os.path.join(DEFAULT_SAVE_PATH, date, json_filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'Detection results not found'}), 404

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

            # 检查是否存在唯一煤块数据
            if 'unique_detections' in data:
                # 返回唯一煤块数据
                return jsonify({
                    'detections': data['unique_detections'],
                    'unique_count': data['unique_count']
                })
            elif 'detections' in data:
                # 向后兼容：如果没有唯一煤块数据，手动处理
                detections = data['detections']

                # 根据track_id聚合（如果存在），或根据位置近似去重
                unique_blocks = {}
                for det in detections:
                    # 如果存在track_id，按ID分组
                    if 'track_id' in det:
                        track_id = det['track_id']
                        if track_id not in unique_blocks:
                            unique_blocks[track_id] = det.copy()
                    else:
                        # 如果没有track_id，尝试使用位置作为近似标识
                        # 这是不太准确的备选方案
                        pos_key = f"{int(det['bbox'][0])}-{int(det['bbox'][1])}"
                        if pos_key not in unique_blocks:
                            unique_blocks[pos_key] = det.copy()

                unique_detections = list(unique_blocks.values())
                return jsonify({
                    'detections': unique_detections,
                    'unique_count': len(unique_detections)
                })
            else:
                return jsonify({'error': 'Invalid detection data format'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 全局错误处理
@app.errorhandler(500)
def internal_error(error):
    print(f"500错误: {str(error)}")
    return jsonify({'error': '服务器内部错误'}), 500


@app.errorhandler(ConnectionError)
def handle_connection_error(error):
    print(f"连接错误: {str(error)}")
    return '', 499  # 客户端关闭请求


# 启动清理任务线程
cleanup_thread = threading.Thread(target=cleanup_tasks)
cleanup_thread.daemon = True
cleanup_thread.start()


# 初始化管理员账户
def init_admin_account():
    from models.user import User
    admin = User.find_by_username('admin')
    if not admin:
        print("创建管理员账户...")
        admin, error = User.create_user(
            username='admin',
            email='admin@system.com',
            password='admin123',
            role='admin'
        )
        if admin:
            print("管理员账户创建成功!")
        else:
            print(f"管理员账户创建失败: {error}")

# 启动应用
if __name__ == '__main__':
    # 确保保存目录存在
    os.makedirs(DEFAULT_SAVE_PATH, exist_ok=True)

    # 初始化管理员账户
    # init_admin_account()

    # 升级现有检测文件
    # upgrade_detection_files()

    print(f"启动煤块检测系统，监控视频将保存至: {DEFAULT_SAVE_PATH}")

    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=False,
        use_reloader=False,
        socket_timeout=3600  # 增加 socket 超时时间
    )