<template>
  <div class="monitor-container">
    <!-- 标题和控制栏 -->
    <div class="monitor-header">
      <div class="controls">
        <el-button-group>
          <el-button 
            type="primary" 
            size="small" 
            icon="el-icon-refresh" 
            @click="refreshAll"
          >刷新</el-button>
          <el-button 
            type="success" 
            size="small" 
            :icon="detectionEnabled ? 'el-icon-video-pause' : 'el-icon-video-play'"
            @click="toggleDetection"
            :loading="toggleLoading"
          >{{ detectionEnabled ? '停止检测' : '开始检测' }}</el-button>
          <el-button 
            type="info" 
            size="small" 
            icon="el-icon-setting"
            @click="showSettings = true"
          >设置</el-button>
        </el-button-group>
      </div>
      
      <!-- 录制状态指示器 -->
      <div class="recording-status" v-if="detectionEnabled">
        <el-tag type="danger" effect="dark">
          <i class="el-icon-video-camera recording-icon"></i>
          录制中: {{ formatTime(recordingTime) }}
        </el-tag>
        <span class="segment-info">当前片段：{{ segmentInfo.currentSegment }}/{{ segmentInfo.totalSegments }}</span>
      </div>
    </div>

    <!-- 监控画面网格 -->
    <div class="video-grid" :class="{ 'single-view': fullscreenIndex !== null }">
      <div 
        v-for="(camera, index) in cameraStatus" 
        :key="index" 
        class="video-item"
        :class="{ 
          'active': index === fullscreenIndex,
          'offline': !camera.connected,
          'detecting': camera.detecting
        }"
      >
        <!-- 视频画面 -->
        <div class="video-wrapper" @click="toggleFullscreen(index)">
          <div class="canvas-container" :style="containerStyle(index)">
            <canvas 
              v-if="camera.connected"
              :ref="'canvas'+index" 
              class="video-canvas"
            ></canvas>
            
            <!-- 未连接状态 -->
            <div v-else class="disconnected-overlay">
              <div class="disconnected-content">
                <i class="el-icon-video-camera-off"></i>
                <p>未连接摄像头</p>
              </div>
            </div>
            
            <!-- 检测结果覆盖层 -->
            <div v-if="camera.detecting && camera.detections.length > 0" class="detection-overlay">
              <div 
                v-for="(detection, idx) in camera.detections" 
                :key="idx"
                class="detection-box"
                :style="{
                  left: `${detection.bbox[0]}%`,
                  top: `${detection.bbox[1]}%`,
                  width: `${detection.bbox[2] - detection.bbox[0]}%`,
                  height: `${detection.bbox[3] - detection.bbox[1]}%`,
                  borderColor: getClassColor(detection.class)
                }"
              >
                <div class="detection-label" :style="{ backgroundColor: getClassColor(detection.class) }">
                  ID:{{ detection.track_id || '?' }} {{ detection.class }} {{ (detection.confidence * 100).toFixed(0) }}%
                </div>
              </div>
            </div>
          </div>
          
          <!-- 状态指示器 -->
          <div class="status-indicator">
            <el-tag 
              size="mini" 
              :type="camera.connected ? 'success' : 'danger'"
            >
              {{ camera.connected ? '在线' : '离线' }}
            </el-tag>
            <el-tag 
              v-if="camera.detecting" 
              size="mini" 
              type="warning"
            >
              检测中
            </el-tag>
            <span class="fps" v-if="camera.connected && showFPS">
              {{ camera.fps || '--' }} FPS
            </span>
          </div>
          
          <!-- 全屏按钮 -->
          <div 
            class="fullscreen-btn" 
            @click.stop="toggleFullscreen(index)"
            v-if="camera.connected"
          >
            <i :class="[
              'el-icon',
              fullscreenIndex === index ? 'el-icon-close' : 'el-icon-full-screen'
            ]"></i>
          </div>
        </div>
        
        <!-- 摄像头信息 -->
        <div class="camera-info">
          <span class="camera-name">监控点 {{ index + 1 }}</span>
          <span class="timestamp" v-if="camera.connected && camera.lastUpdate">
            {{ formatTime(camera.lastUpdate) }}
          </span>
        </div>
        
        <!-- 检测结果摘要 -->
        <div v-if="camera.detecting && camera.connected" class="detection-summary">
          <div class="detection-count">
            <i class="el-icon-aim"></i> 
            唯一煤块数: <strong>{{ camera.uniqueCount || 0 }}</strong>
            <span class="current-count">(当前帧: {{ camera.currentFrameCount || 0 }})</span>
          </div>
          <el-tooltip v-if="camera.latestSavedVideo" effect="dark" :content="camera.latestSavedVideo" placement="bottom">
            <div class="saved-indicator">
              <i class="el-icon-video-camera"></i>
              <span>最近保存: {{ formatSavedTime(camera.latestSavedTime) }}</span>
            </div>
          </el-tooltip>
        </div>
      </div>
    </div>

    <!-- 设置对话框 -->
    <el-dialog title="监控设置" :visible.sync="showSettings" width="30%">
      <el-form label-width="160px">
        <el-form-item label="显示FPS">
          <el-switch v-model="showFPS"></el-switch>
        </el-form-item>
        <el-form-item label="布局列数">
          <el-select v-model="gridColumns" style="width: 100%">
            <el-option :value="3" label="3列"></el-option>
            <el-option :value="4" label="4列"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="检测灵敏度">
          <el-slider v-model="detectionSensitivity" :min="10" :max="90"></el-slider>
        </el-form-item>
        <el-form-item label="视频保存路径">
          <el-input v-model="videoSavePath" readonly>
            <el-button slot="append" icon="el-icon-folder-opened" @click="openSaveFolder">打开</el-button>
          </el-input>
        </el-form-item>
      </el-form>
    </el-dialog>
  </div>
</template>

<script>
import io from 'socket.io-client';
import dayjs from 'dayjs';
import { mapGetters, mapActions } from 'vuex';

export default {
  data() {
    return {
      cameraStatus: Array(9).fill().map(() => ({
        connected: false, 
        lastUpdate: null, 
        fps: 0, 
        frameCount: 0, 
        lastFpsTime: null,
        detecting: false,
        detections: [],
        detectionCount: 0,
        latestSavedVideo: null,
        latestSavedTime: null
      })),
      videoAspectRatios: Array(9).fill(16/9), // 存储每个摄像头的宽高比
      fullscreenIndex: null,
      socket: null,
      showSettings: false,
      showFPS: true,
      gridColumns: 3,
      fpsInterval: null,
      
      // 检测相关属性
      toggleLoading: false,
      detectionSensitivity: 50,
      showDetectionBoxes: true,
      videoSavePath: 'D:\\SurveillanceVideo',
      recordingInterval: null,
      baseURL: process.env.VUE_APP_API_URL || 'http://localhost:5000'
    }
  },
  computed: {
    ...mapGetters([
      'isDetecting',
      'recordingTime',
      'segmentInfo'
    ]),
    detectionEnabled: {
      get() {
        return this.isDetecting;
      },
      set(value) {
        // 由toggleDetection方法处理
      }
    },
    gridTemplateColumns() {
      return `repeat(${this.gridColumns}, 1fr)`;
    },
    containerStyle() {
      return (index) => {
        const aspectRatio = this.videoAspectRatios[index];
        return {
          paddingBottom: `${100 / aspectRatio}%`,
          position: 'relative',
          width: '100%',
          height: '0'
        };
      };
    },
    // 获取检测状态的摄像头ID数组
    activeCameraIds() {
      return this.cameraStatus
        .map((camera, index) => camera.detecting ? index : -1)
        .filter(id => id !== -1);
    }
  },
  mounted() {
    this.initSocketConnection();
    this.startFpsCounter();
    
    // 如果当前有检测在进行，将UI状态同步到实际状态
    if (this.isDetecting) {
      this.syncDetectionState();
    }
  },
  beforeDestroy() {
    this.disconnectAllCameras();
    if (this.socket) {
      this.socket.disconnect();
    }
    clearInterval(this.fpsInterval);
    this.stopRecordingTimer();
  },
  methods: {
    ...mapActions([
      'startDetection',
      'stopDetection',
      'updateRecordingTime',
      'updateSegmentInfo'
    ]),
    // 同步检测状态
    syncDetectionState() {
      // 从Vuex获取记录状态，更新UI
      const activeCameras = this.$store.getters.activeCameras;
      
      // 更新本地摄像头状态
      activeCameras.forEach(cameraId => {
        if (cameraId >= 0 && cameraId < this.cameraStatus.length) {
          this.$set(this.cameraStatus[cameraId], 'detecting', true);
        }
      });
      
      // 启动时间更新计时器
      this.startRecordingTimer();
    },
    initSocketConnection() {
      this.socket = io(this.baseURL);
      
      this.socket.on('connect', () => {
        console.log('WebSocket connected');
        this.initCameraStreams();
      });
      
      this.socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
        this.cameraStatus.forEach((camera, index) => {
          this.$set(this.cameraStatus[index], 'connected', false);
        });
      });
      
      // 为每个摄像头设置帧接收处理
      for (let i = 0; i < this.cameraStatus.length; i++) {
        this.socket.on(`video_frame_${i}`, (data) => {
          this.handleFrame(i, data.frame, data.timestamp);
        });
        
        // 新增检测结果接收处理
        this.socket.on(`detection_result_${i}`, (data) => {
          this.handleDetectionResult(i, data);
        });
      }
      
      // 监听视频保存事件
      this.socket.on('video_saved', (data) => {
        const { camera_id, file_path, timestamp } = data;
        if (camera_id >= 0 && camera_id < this.cameraStatus.length) {
          this.$set(this.cameraStatus[camera_id], 'latestSavedVideo', file_path);
          this.$set(this.cameraStatus[camera_id], 'latestSavedTime', timestamp);
          
          // 更新当前片段信息 - 现在通过Vuex来管理
          if (camera_id === 0 && this.isDetecting) { // 主要针对第一个摄像头
            this.updateSegmentInfo({
              currentSegment: this.segmentInfo.currentSegment + 1,
              totalSegments: 24 * 4 // 假设每天分段数为24小时 * 4段/小时
            });
          }
        }
      });
    },
    initCameraStreams() {
      // 只连接1个摄像头作为示例
      for (let i = 0; i < 1; i++) {
        this.connectCamera(i);
      }
    },
    connectCamera(index) {
      if (!this.socket || !this.socket.connected) return;
      
      this.socket.emit('start_stream', { camera_id: index });
      this.$set(this.cameraStatus[index], 'connected', true);
      this.$set(this.cameraStatus[index], 'lastUpdate', new Date());
    },
    disconnectAllCameras() {
      if (!this.socket || !this.socket.connected) return;
      
      for (let i = 0; i < this.cameraStatus.length; i++) {
        this.socket.emit('stop_stream', { camera_id: i });
        this.$set(this.cameraStatus[i], 'connected', false);
      }
    },
    handleFrame(index, frameData, timestamp) {
      const canvas = this.$refs[`canvas${index}`]?.[0];
      if (!canvas) return;
      
      const ctx = canvas.getContext('2d');
      const container = canvas.parentElement;
      
      const img = new Image();
      img.onload = () => {
        // 计算并保存视频原始宽高比
        const aspectRatio = img.width / img.height;
        this.videoAspectRatios[index] = aspectRatio;
        
        // 设置canvas尺寸匹配容器
        const containerWidth = container.clientWidth;
        const containerHeight = containerWidth / aspectRatio;
        
        canvas.width = containerWidth;
        canvas.height = containerHeight;
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        
        // 更新FPS计数
        this.$set(this.cameraStatus[index], 'frameCount', this.cameraStatus[index].frameCount + 1);
        this.$set(this.cameraStatus[index], 'lastUpdate', new Date(timestamp * 1000));
      };
      img.src = `data:image/jpeg;base64,${frameData}`;
    },
    handleDetectionResult(index, data) {
      const { detections, count, current_count } = data;
      
      // 更新检测结果
      this.$set(this.cameraStatus[index], 'detections', detections);
      
      // 更新唯一煤块计数和当前帧计数
      this.$set(this.cameraStatus[index], 'uniqueCount', count);
      this.$set(this.cameraStatus[index], 'currentFrameCount', current_count);
  
      // 不再累加检测计数，而是直接使用统计的唯一煤块数
      this.$set(this.cameraStatus[index], 'detectionCount', count);
  
    },
    toggleFullscreen(index) {
      if (!this.cameraStatus[index].connected) return;
      
      if (this.fullscreenIndex === index) {
        this.fullscreenIndex = null;
      } else {
        this.fullscreenIndex = index;
      }
    },
    refreshAll() {
      this.disconnectAllCameras();
      setTimeout(() => {
        this.initCameraStreams();
      }, 500);
    },
    formatTime(time) {
      if (time instanceof Date) {
        return dayjs(time).format('HH:mm:ss');
      } else {
        const totalSeconds = Math.floor(time / 1000);
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;
        
        const pad = (num) => num.toString().padStart(2, '0');
        return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
      }
    },
    formatSavedTime(time) {
      if (!time) return '--';
      return dayjs(time * 1000).format('HH:mm:ss');
    },
    startFpsCounter() {
      this.fpsInterval = setInterval(() => {
        const now = Date.now();
        this.cameraStatus.forEach((camera, index) => {
          if (camera.connected) {
            if (!camera.lastFpsTime || now - camera.lastFpsTime >= 1000) {
              this.$set(this.cameraStatus[index], 'fps', camera.frameCount);
              this.$set(this.cameraStatus[index], 'frameCount', 0);
              this.$set(this.cameraStatus[index], 'lastFpsTime', now);
            }
          }
        });
      }, 1000);
    },
    // 新增方法：切换检测状态
    async toggleDetection() {
      if (!this.socket || !this.socket.connected) {
        this.$message.error('WebSocket未连接，无法开启检测');
        return;
      }
      
      this.toggleLoading = true;
      
      try {
        if (this.isDetecting) {
          // 停止检测
          await this.stopDetectionProcess();
        } else {
          // 启动检测
          await this.startDetectionProcess();
        }
      } catch (error) {
        console.error('切换检测状态失败:', error);
        this.$message.error(`切换检测状态失败: ${error.message || '未知错误'}`);
      } finally {
        this.toggleLoading = false;
      }
    },
    async startDetectionProcess() {
      // 为每个已连接的摄像头开启检测
      const promises = [];
      const activeCameraIds = [];
      
      for (let i = 0; i < this.cameraStatus.length; i++) {
        if (this.cameraStatus[i].connected) {
          promises.push(this.startCameraDetection(i));
          activeCameraIds.push(i);
        }
      }
      
      await Promise.all(promises);
      
      // 更新全局状态
      this.startDetection(activeCameraIds);
      
      // 开始录制计时器
      this.startRecordingTimer();
      
      this.$message.success('检测已开启');
    },
    async startCameraDetection(index) {
      return new Promise((resolve, reject) => {
        this.socket.emit('start_detection', {
          camera_id: index,
          sensitivity: this.detectionSensitivity / 100,
          save_path: this.videoSavePath
        }, (response) => {
          if (response.success) {
            this.$set(this.cameraStatus[index], 'detecting', true);
            resolve();
          } else {
            reject(new Error(response.error || `无法开启摄像头 ${index + 1} 的检测`));
          }
        });
      });
    },
    async stopDetectionProcess() {
      // 为每个正在检测的摄像头停止检测
      const promises = [];
      
      for (let i = 0; i < this.cameraStatus.length; i++) {
        if (this.cameraStatus[i].detecting) {
          promises.push(this.stopCameraDetection(i));
        }
      }
      
      await Promise.all(promises);
      
      // 更新全局状态
      this.stopDetection();
      
      // 停止录制计时器
      this.stopRecordingTimer();
      
      this.$message.success('检测已停止');
    },
    async stopCameraDetection(index) {
      return new Promise((resolve, reject) => {
        this.socket.emit('stop_detection', {
          camera_id: index
        }, (response) => {
          if (response.success) {
            this.$set(this.cameraStatus[index], 'detecting', false);
            resolve();
          } else {
            reject(new Error(response.error || `无法停止摄像头 ${index + 1} 的检测`));
          }
        });
      });
    },
    getClassColor(className) {
      // 根据类别名称返回不同颜色
      const colors = {
        'coal': '#f56c6c',   // 红色
        'rock': '#e6a23c',   // 橙色
        'default': '#409eff' // 蓝色
      };
      
      return colors[className] || colors.default;
    },
    startRecordingTimer() {
      // 不再创建新计时器，而是使用单一计时器更新Vuex状态
      this.recordingInterval = setInterval(() => {
        // 更新Vuex中的时间
        this.updateRecordingTime(this.recordingTime + 1000);
      }, 1000);
    },
    stopRecordingTimer() {
      if (this.recordingInterval) {
        clearInterval(this.recordingInterval);
        this.recordingInterval = null;
      }
    },
    openSaveFolder() {
      // 通知后端打开保存文件夹
      this.socket.emit('open_save_folder', { path: this.videoSavePath });
    }
  }
}
</script>

<style scoped>
.monitor-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #f0f2f5;
  padding: 20px;
  box-sizing: border-box;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.recording-status {
  display: flex;
  align-items: center;
  gap: 10px;
}

.recording-icon {
  animation: pulse 1.5s infinite;
}

.segment-info {
  font-size: 12px;
  color: #606266;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}

.video-grid {
  flex: 1;
  display: grid;
  gap: 15px;
  transition: all 0.3s ease;
  grid-template-columns: v-bind(gridTemplateColumns);
  grid-auto-rows: minmax(280px, 1fr);
  overflow-y: auto;
  padding-bottom: 20px;
}

.video-grid.single-view {
  grid-template-columns: 1fr;
  grid-auto-rows: 1fr;
}

.video-item {
  display: flex;
  flex-direction: column;
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  overflow: hidden;
  transition: all 0.3s ease;
  height: auto;
  min-height: 280px;
}

.video-item.active {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2000;
  margin: 0;
  border-radius: 0;
  height: auto;
}

.video-item.offline {
  opacity: 0.8;
}

.video-item.detecting {
  border: 2px solid #67c23a;
}

.video-wrapper {
  position: relative;
  flex: 1;
  background-color: #000;
  cursor: pointer;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.canvas-container {
  width: 100%;
  position: relative;
  background-color: #000;
}

.video-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.video-item.active .canvas-container {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  padding-bottom: 0;
  z-index: 2000;
}

.video-item.active .video-canvas {
  object-fit: contain;
}

.disconnected-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(0, 0, 0, 0.7);
  color: #fff;
}

.disconnected-content {
  text-align: center;
  padding: 20px;
}

.disconnected-content i {
  font-size: 40px;
  margin-bottom: 10px;
  color: #909399;
}

.disconnected-content p {
  margin: 0;
  font-size: 16px;
  color: #c0c4cc;
}

.detection-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.detection-box {
  position: absolute;
  border: 2px solid;
  box-sizing: border-box;
}

.detection-label {
  position: absolute;
  top: -20px;
  left: 0;
  padding: 2px 5px;
  color: white;
  font-size: 12px;
  white-space: nowrap;
  border-radius: 2px;
}

.status-indicator {
  position: absolute;
  top: 8px;
  left: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  z-index: 10;
}

.status-indicator .fps {
  color: #fff;
  font-size: 12px;
  background-color: rgba(0, 0, 0, 0.5);
  padding: 2px 6px;
  border-radius: 3px;
}

.fullscreen-btn {
  position: absolute;
  bottom: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  background-color: rgba(0, 0, 0, 0.5);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  cursor: pointer;
  transition: all 0.2s;
  z-index: 10;
}

.fullscreen-btn:hover {
  background-color: rgba(0, 0, 0, 0.7);
}

.fullscreen-btn i {
  font-size: 14px;
}

.camera-info {
  padding: 8px 12px;
  background-color: #f5f7fa;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #606266;
  border-top: 1px solid #ebeef5;
}

.camera-name {
  font-weight: bold;
}

.timestamp {
  color: #909399;
}

.detection-summary {
  padding: 8px 12px;
  background-color: #f0f9eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #67c23a;
  border-top: 1px solid #e1f3d8;
}

.detection-count {
  display: flex;
  align-items: center;
  gap: 5px;
}

.saved-indicator {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #909399;
  cursor: help;
}

/* 响应式布局 */
@media (max-width: 1200px) {
  .video-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 992px) {
  .video-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .video-grid {
    grid-template-columns: 1fr;
  }
}
</style>