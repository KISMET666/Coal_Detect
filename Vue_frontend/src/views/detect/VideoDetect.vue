<template>
  <div class="video-detect-container">
    <el-upload
      class="upload-demo"
      action=""
      :auto-upload="false"
      :on-change="handleVideoChange"
      :show-file-list="false"
    >
      <el-button type="primary">选择视频</el-button>
    </el-upload>
    
    <!-- 现有的加载状态显示保持不变 -->
    <div v-if="loading" class="loading">
        <el-progress type="circle" :percentage="progress"></el-progress>
        <p>{{ loadingMessage }}</p>
        <p v-if="taskStatus === 'processing'" class="task-status">
          任务正在后台运行，请勿关闭页面
        </p>
      </div>
    <!-- 视频调试信息区域 -->
    <div v-if="resultVideo" class="debug-info">
      <p><strong>视频URL：</strong> <code>{{ resultVideo }}</code></p>
      <p>
        <a :href="resultVideo" target="_blank">直接访问视频</a> |  
        <el-button type="text" @click="validateVideo">验证视频</el-button>
      </p>
      <p v-if="taskId"><strong>任务ID：</strong> {{ taskId }}</p>
      <p v-if="videoErrorInfo"><strong>错误信息：</strong> {{ videoErrorInfo }}</p>
    </div>
    
    <div v-if="resultVideo" class="result-container">
      <h3>检测结果</h3>
      <!-- 主视频播放器 -->
      <video 
        ref="videoPlayer"
        :src="resultVideo" 
        controls 
        class="result-video"
        @error="handleVideoError"
      ></video>
      
      <!-- 备用HTML5视频播放器 -->
      <div v-if="showFallbackPlayer" class="fallback-player">
        <h4>备用播放器</h4>
        <video 
          ref="fallbackPlayer"
          controls 
          class="result-video"
          @error="handleFallbackError"
        >
          <source :src="resultVideo" type="video/mp4">
          您的浏览器不支持视频播放
        </video>
      </div>
      
      <!-- 添加检测结果汇总区域 -->
      <div v-if="!loading && summary.total_count > 0" class="detection-summary">
        <el-card class="summary-card">
          <div slot="header">
            <span>煤块检测汇总</span>
          </div>
          
          <el-row :gutter="20">
            <el-col :span="8">
              <div class="stat-item">
                <div class="stat-title">总煤块数</div>
                <div class="stat-value">{{ summary.total_count }}</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="stat-item">
                <div class="stat-title">视频时长</div>
                <div class="stat-value">{{ summary.video_duration ? summary.video_duration.toFixed(2) + '秒' : '--' }}</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="stat-item">
                <div class="stat-title">平均置信度</div>
                <div class="stat-value">{{ summary.average_confidence ? (summary.average_confidence * 100).toFixed(2) + '%' : '--' }}</div>
              </div>
            </el-col>
          </el-row>
          
          <el-divider>大小分布</el-divider>
          
          <div class="size-chart">
            <div class="size-bar">
              <div class="size-segment size-small" 
                  :style="{width: getSizePercentage('small') + '%'}" 
                  v-if="summary.size_distribution.small > 0">
                小型: {{ summary.size_distribution.small }}
              </div>
              <div class="size-segment size-medium" 
                  :style="{width: getSizePercentage('medium') + '%'}" 
                  v-if="summary.size_distribution.medium > 0">
                中型: {{ summary.size_distribution.medium }}
              </div>
              <div class="size-segment size-large" 
                  :style="{width: getSizePercentage('large') + '%'}" 
                  v-if="summary.size_distribution.large > 0">
                大型: {{ summary.size_distribution.large }}
              </div>
            </div>
          </div>
          
          <!-- 帧分布图 -->
          <el-divider>煤块出现分布</el-divider>
          <div class="frame-distribution">
            <div v-for="(count, range) in summary.frame_distribution" 
                :key="range" 
                class="frame-segment">
              <div class="frame-label">{{ range }} 帧</div>
              <el-progress 
                :percentage="getFramePercentage(count)" 
                :format="() => count + '个煤块'" 
                :stroke-width="18">
              </el-progress>
            </div>
          </div>
          
          <!-- 导出按钮 -->
          <div class="action-buttons">
            <el-button 
              type="primary" 
              icon="el-icon-download" 
              @click="exportToCSV">
              导出CSV
            </el-button>
            <el-button 
              type="success" 
              icon="el-icon-download" 
              @click="exportToExcel">
              导出Excel
            </el-button>
            <el-button 
              type="info" 
              icon="el-icon-view" 
              @click="loadFullDetails"
              :loading="loadingDetails"
              v-if="hasMoreDetections && !detailsLoaded">
              加载完整数据
            </el-button>
          </div>
        </el-card>
      </div>
      
      <!-- 检测结果表格 -->
      <div v-if="detections.length > 0" class="detection-table">
        <el-card>
          <div slot="header">
            <span>煤块详细信息</span>
            <span class="detail-count">
              {{ detailsLoaded ? `显示全部 ${detections.length} 个` : `显示 ${detections.length} 个(共 ${summary.total_count} 个)` }}
            </span>
          </div>
          
          <!-- 表格 -->
          <el-table :data="paginatedDetections" border style="width: 100%" stripe>
            <el-table-column prop="track_id" label="煤块ID" width="90" align="center"></el-table-column>
            <el-table-column prop="confidence" label="置信度" width="120" align="center">
              <template #default="{row}">
                <el-tag :type="getConfidenceType(row.confidence)">
                  {{ (row.confidence * 100).toFixed(2) }}%
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="出现帧范围" width="150" align="center">
              <template #default="{row}">
                {{ row.first_frame || 0 }} - {{ row.last_frame || 0 }}
              </template>
            </el-table-column>
            <el-table-column label="尺寸估计" width="100" align="center">
              <template #default="{row}">
                <el-tag :type="getSizeTagType(row.bbox)">
                  {{ estimateSize(row.bbox) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="bbox" label="位置坐标" align="center">
              <template #default="{row}">
                <el-popover
                  placement="top"
                  width="200"
                  trigger="hover"
                >
                  <div class="bbox-details">
                    <p>左上角: ({{ Math.round(row.bbox[0]) }}, {{ Math.round(row.bbox[1]) }})</p>
                    <p>右下角: ({{ Math.round(row.bbox[2]) }}, {{ Math.round(row.bbox[3]) }})</p>
                    <p>宽度: {{ Math.round(row.bbox[2] - row.bbox[0]) }}px</p>
                    <p>高度: {{ Math.round(row.bbox[3] - row.bbox[1]) }}px</p>
                  </div>
                  <el-button slot="reference" type="text">
                    [{{ row.bbox.map(x => Math.round(x)).join(', ') }}]
                  </el-button>
                </el-popover>
              </template>
            </el-table-column>
          </el-table>
          
          <!-- 分页控件 -->
          <div class="pagination" v-if="detections.length > pageSize">
            <el-pagination
              @current-change="handleCurrentChange"
              @size-change="handleSizeChange"
              :current-page="currentPage"
              :page-sizes="[5, 10, 20, 50]"
              :page-size="pageSize"
              layout="total, sizes, prev, pager, next, jumper"
              :total="detections.length">
            </el-pagination>
          </div>
          
          <!-- 如果还有更多数据但尚未加载 -->
          <div v-if="hasMoreDetections && !detailsLoaded" class="more-data-hint">
            <el-alert
              title="当前仅显示部分煤块数据，点击上方“加载完整数据””以加载更多数据，或等待后台任务完成。" 
              type="info"
              show-icon>
            </el-alert>
          </div>
        </el-card>
      </div>
      
      
    </div>
  </div>
</template>

<script>
// import axios from 'axios';
import io from 'socket.io-client';
import { apiService } from '@/services/api';
import { saveAs } from 'file-saver';
import * as XLSX from 'xlsx';

export default {
  data() {
    return {
      resultVideo: null,
      detections: [],
      loading: false,
      progress: 0,
      showFallbackPlayer: false,
      videoErrorInfo: null,
      responseData: null, // 保存完整的响应数据用于调试
      taskId: null,       // 异步任务ID
      taskStatus: null,   // 任务状态
      taskCheckInterval: null, // 轮询任务状态的计时器
      socket: null,       // WebSocket连接
      loadingMessage: '正在上传视频...',
      baseURL: process.env.VUE_APP_API_URL || 'http://127.0.0.1:5000',

      // 新增属性
      loadingDetails: false,
      hasMoreDetections: false,
      detailsLoaded: false,
      uniqueCount: 0,
      summary: {
        total_count: 0,
        total_frames: 0,
        video_duration: 0,
        average_confidence: 0,
        size_distribution: {
          small: 0,
          medium: 0,
          large: 0
        },
        frame_distribution: {}
      },
      currentPage: 1,
      pageSize: 10,
      totalItems: 0
      }
  },
  mounted() {
    // 初始化WebSocket连接
    this.initSocket();
  },
  beforeDestroy() {
    // 清理轮询和WebSocket连接
    this.clearTaskInterval();
    if (this.socket) {
      this.socket.disconnect();
    }
  },
  computed: {
    // 分页数据
    paginatedDetections() {
      const start = (this.currentPage - 1) * this.pageSize;
      const end = Math.min(start + this.pageSize, this.detections.length);
      return this.detections.slice(start, end);
    }
  },
  methods: {
    // 初始化WebSocket连接，用于接收任务进度更新
    initSocket() {
      this.socket = io(this.baseURL);
      
      this.socket.on('connect', () => {
        console.log('WebSocket连接成功');
      });
      
      this.socket.on('video_progress', (data) => {
        // 确保收到的任务进度是当前任务的
        if (data.task_id === this.taskId) {
          console.log('收到任务进度更新:', data.progress);
          this.progress = Math.round(data.progress);
          this.loadingMessage = `视频处理中... ${this.progress}%`;
        }
      });
      
      this.socket.on('task_completed', (data) => {
        if (data.task_id === this.taskId) {
          console.log('任务完成！调用fetchTaskResult()');
          this.fetchTaskResult();
        }
      });
      
      this.socket.on('task_failed', (data) => {
        if (data.task_id === this.taskId) {
          console.error('任务失败:', data.error);
          this.loading = false;
          this.taskStatus = 'failed';
          this.$message.error('视频处理失败: ' + data.error);
        }
      });
      
      this.socket.on('disconnect', () => {
        console.log('WebSocket连接断开');
      });
    },
    
    getConfidenceType(confidence) {
      const percent = confidence * 100;
      if (percent >= 80) return 'success';
      if (percent >= 60) return 'warning';
      return 'danger';
    },

    getSizeTagType(bbox) {
      if (!bbox || bbox.length < 4) return 'info';
      
      const area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]);
      
      if (area < 5000) return 'info';
      if (area < 20000) return 'warning';
      return 'danger';
    },
    // 视频元素错误处理
    handleVideoError(event) {
      console.error('视频播放失败:', event);
      
      // 获取详细错误信息
      const videoElement = this.$refs.videoPlayer;
      if (videoElement) {
        const errorCodes = [
          '未知错误',
          '用户终止',
          '网络错误',
          '解码错误',
          '格式不支持'
        ];
        
        const error = videoElement.error;
        if (error) {
          this.videoErrorInfo = `错误代码: ${error.code} - ${errorCodes[error.code] || '未知'}, 
                                详情: ${error.message || '无详情'}`;
        } else {
          this.videoErrorInfo = '视频元素报告了错误，但无详细信息';
        }
      }
      
      this.$message.error('视频播放失败，正在尝试备用播放器');
      this.showFallbackPlayer = true; // 显示备用播放器
    },
    
    // 备用播放器错误处理
    handleFallbackError(event) {
      console.error('备用播放器也失败了:', event);
      this.videoErrorInfo += ' | 备用播放器也失败';
      this.$message.error('备用播放器也失败了，请检查视频格式和服务器配置');
    },
    
    // 处理视频文件选择和上传
    async handleVideoChange(file) {
      this.loading = true;
      this.progress = 0;
      this.videoErrorInfo = null;
      this.showFallbackPlayer = false;
      this.resultVideo = null;
      this.detections = [];
      this.taskId = null;
      this.taskStatus = null;
      this.loadingMessage = '正在上传视频...';
      
      try {
        const formData = new FormData();
        formData.append('file', file.raw);
        
        console.log('正在上传视频到:', `${this.baseURL}/api/detect/video`);
        const response = await apiService.post(`/api/detect/video`, formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          },
          onUploadProgress: (progressEvent) => {
            this.progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          },
          timeout: 300000
        });
        
        // 保存完整响应用于调试
        this.responseData = response.data;
        console.log('后端完整响应:', response.data);
        
        // 检查是否收到任务ID
        if (response.data.task_id) {
          this.taskId = response.data.task_id;
          this.taskStatus = 'processing';
          this.loadingMessage = '视频处理中... 0%';
          this.startTaskPolling();
        } else if (response.data.result_url) {
          // 老版本API直接返回结果
          console.log('收到老版本API直接结果:', response.data.result_url);
          this.handleDirectResponse(response.data);
        } else {
          throw new Error('后端响应异常，既无任务ID也无结果URL');
        }
      } catch (error) {
        console.error('视频检测失败:', error);
        this.$message.error('检测失败: ' + (error.response?.data?.error || error.message || '未知错误'));
        this.loading = false;
      }
    },
    
    // 开始轮询任务状态
    startTaskPolling() {
      this.clearTaskInterval();
      
      this.taskCheckInterval = setInterval(() => {
        this.checkTaskStatus();
      }, 2000); // 每2秒检查一次
    },
    
    // 清除任务轮询计时器
    clearTaskInterval() {
      if (this.taskCheckInterval) {
        clearInterval(this.taskCheckInterval);
        this.taskCheckInterval = null;
      }
    },
    
    // 检查任务状态
    async checkTaskStatus() {
      if (!this.taskId) return;
      
      try {
        const response = await apiService.get(`/api/task/${this.taskId}`);
        console.log('任务状态:', response.data);
        
        this.taskStatus = response.data.status;
        
        if (response.data.status === 'processing') {
          // 更新进度
          this.progress = Math.round(response.data.progress || 0);
          this.loadingMessage = `视频处理中... ${this.progress}%`;
        } else if (response.data.status === 'completed') {
          // 任务完成，获取结果
          this.clearTaskInterval();
          this.handleDirectResponse(response.data);
          console.log('在checkTaskStatus()中调用handleDirectResponse');
        } else if (response.data.status === 'failed') {
          // 任务失败
          this.clearTaskInterval();
          this.loading = false;
          this.$message.error('视频处理失败: ' + (response.data.error || '未知错误'));
        }
      } catch (error) {
        console.error('检查任务状态失败:', error);
        // 轮询失败不要立即停止，可能是临时网络问题
        this.$message.warning('检查任务状态失败，将在稍后重试');
      }
    },
    
    // 直接获取任务结果
    async fetchTaskResult() {
      if (!this.taskId) return;
      
      try {
        const response = await apiService.get(`/api/task/${this.taskId}`);
        
        if (response.data.status === 'completed') {
          this.handleDirectResponse(response.data);
          // 保存唯一煤块计数
          this.uniqueCount = response.data.unique_count || 0;
          console.log('视频中唯一煤块数量:', this.uniqueCount);
          console.log('通过WebSocket获取任务结果');
        } else if (response.data.status === 'failed') {
          this.loading = false;
          this.$message.error('视频处理失败: ' + (response.data.error || '未知错误'));
        } else {
          this.startTaskPolling(); // 继续轮询直到任务完成
        }
      } catch (error) {
        console.error('获取任务结果失败:', error);
        this.$message.error('获取任务结果失败: ' + error.message);
        this.loading = false;
      }
    },
    
    // 处理直接返回的响应（兼容旧API或任务完成后）
    handleDirectResponse(data) {
      if (data.result_url) {
        // 如果结果URL是相对路径，添加基础URL
        if (data.result_url.startsWith('/')) {
          this.resultVideo = `${this.baseURL}${data.result_url}?t=${Date.now()}`;
        } else {
          this.resultVideo = `${data.result_url}?t=${Date.now()}`;
        }
        
        console.log('最终视频URL:', this.resultVideo);
        // 保存检测结果和汇总数据
        this.detections = data.detections || [];
        this.hasMoreDetections = data.has_more_detections || false;
        this.uniqueCount = data.unique_count || 0;
        this.summary = data.summary || {
          total_count: data.unique_count || 0,
          total_frames: 0,
          video_duration: 0,
          average_confidence: 0,
          size_distribution: { small: 0, medium: 0, large: 0 },
          frame_distribution: {}
        };
        
        this.totalItems = this.summary.total_count;
        this.detailsLoaded = !this.hasMoreDetections;
        this.loading = false;
        
        this.$message.success(`视频处理完成! 检测到${this.uniqueCount}个煤块`);

        // 添加视频预加载处理
        this.$nextTick(() => {
          const videoElement = this.$refs.videoPlayer;
          if (videoElement) {
            videoElement.addEventListener('loadstart', () => console.log('开始加载视频'));
            videoElement.addEventListener('loadeddata', () => console.log('视频数据加载完成'));
            videoElement.addEventListener('canplaythrough', () => console.log('视频可以流畅播放'));
            
            // 设置视频缓冲优先级
            videoElement.preload = 'auto';
          }
        });
      } else {
        this.$message.error('后端未返回有效的视频URL');
        this.loading = false;
      }
    },
    
    // 验证视频URL是否可访问
    validateVideo() {
      if (!this.resultVideo) return;
      
      console.log('正在验证视频URL:', this.resultVideo);
      
      // 检查当前视频元素状态
      const videoElement = this.$refs.videoPlayer;
      if (videoElement) {
        console.log('视频元素网络状态:', videoElement.networkState);
        console.log('视频元素准备状态:', videoElement.readyState);
        console.log('视频元素错误对象:', videoElement.error);
      }
      
      // 测试通过XHR直接获取视频
      this.$message.info('正在测试视频URL可访问性...');
      apiService.get(this.resultVideo, { responseType: 'blob' })
        .then(response => {
          console.log('视频URL可访问:', response.status);
          console.log('内容类型:', response.headers['content-type']);
          console.log('内容大小:', response.data.size, '字节');
          
          this.$message.success(`视频URL可访问! 状态: ${response.status}, 大小: ${(response.data.size/1024).toFixed(2)}KB`);
          
          // 如果视频可以获取但不能播放，可能是编码问题
          if (response.data.size > 0 && this.videoErrorInfo) {
            this.$message.warning('视频文件存在且可获取，但播放器无法播放，可能是编码格式不兼容');
          }
          
          // 尝试通过URL.createObjectURL创建一个新的视频源
          if (this.videoErrorInfo) {
            const blob = new Blob([response.data], { type: 'video/mp4' });
            const blobUrl = URL.createObjectURL(blob);
            console.log('创建Blob URL:', blobUrl);
            
            // 如果已显示备用播放器，使用blob URL
            if (this.showFallbackPlayer && this.$refs.fallbackPlayer) {
              this.$refs.fallbackPlayer.src = blobUrl;
              this.$refs.fallbackPlayer.load();
              this.$refs.fallbackPlayer.play();
            }
          }
        })
        .catch(error => {
          console.error('视频URL测试失败:', error);
          this.$message.error('无法访问视频URL: ' + error.message);
        });
    },
    
    // 加载完整数据
    async loadFullDetails() {
      if (this.detailsLoaded || !this.taskId) return;
      
      this.loadingDetails = true;
      
      try {
        const response = await apiService.get(`/api/task/${this.taskId}?details=true`);
        
        if (response.data.detections) {
          this.detections = response.data.detections;
          this.detailsLoaded = true;
          this.hasMoreDetections = false;
          this.$message.success('已加载完整煤块数据');
        }
      } catch (error) {
        console.error('加载完整数据失败:', error);
        this.$message.error('加载完整数据失败: ' + error.message);
      } finally {
        this.loadingDetails = false;
      }
    },

    // 分页方法
    handleCurrentChange(page) {
      this.currentPage = page;
    },

    handleSizeChange(size) {
      this.pageSize = size;
      this.currentPage = 1; // 重置到第一页
    },

    // 计算煤块大小类别
    estimateSize(bbox) {
      if (!bbox || bbox.length < 4) return '未知';
      
      const area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]);
      
      if (area < 5000) return '小型';
      if (area < 20000) return '中型';
      return '大型';
    },

    // 计算大小分布百分比
    getSizePercentage(size) {
      const total = this.summary.size_distribution.small + 
                    this.summary.size_distribution.medium + 
                    this.summary.size_distribution.large;
      if (total === 0) return 0;
      
      return (this.summary.size_distribution[size] / total) * 100;
    },

    // 计算帧分布百分比
    getFramePercentage(count) {
      if (this.summary.total_count === 0) return 0;
      return (count / this.summary.total_count) * 100;
    },

    // 导出为CSV
    exportToCSV() {
      if (!this.detections || this.detections.length === 0) {
        this.$message.warning('没有可导出的数据');
        return;
      }
      
      // 如果未加载完整数据，先询问用户
      if (this.hasMoreDetections && !this.detailsLoaded) {
        this.$confirm('当前仅加载了部分数据，是否先加载完整数据再导出?', '提示', {
          confirmButtonText: '加载并导出',
          cancelButtonText: '仅导出当前数据',
          type: 'warning'
        }).then(() => {
          // 先加载完整数据
          this.loadFullDetails().then(() => {
            this.performCSVExport();
          });
        }).catch(() => {
          // 直接导出当前数据
          this.performCSVExport();
        });
      } else {
        // 已有完整数据，直接导出
        this.performCSVExport();
      }
    },

    // 执行CSV导出
    performCSVExport() {
      // 准备CSV数据
      const csvData = [
        // 表头
        ['煤块ID', '置信度', '首次出现帧', '最后出现帧', '尺寸估计', '边界框坐标X1', '边界框坐标Y1', '边界框坐标X2', '边界框坐标Y2']
      ];
      
      // 添加数据行
      this.detections.forEach(det => {
        csvData.push([
          det.track_id,
          (det.confidence * 100).toFixed(2) + '%',
          det.first_frame || 0,
          det.last_frame || 0,
          this.estimateSize(det.bbox),
          Math.round(det.bbox[0]),
          Math.round(det.bbox[1]),
          Math.round(det.bbox[2]),
          Math.round(det.bbox[3])
        ]);
      });
      
      // 添加汇总信息
      csvData.push([]);
      csvData.push(['汇总信息']);
      csvData.push(['总煤块数', this.summary.total_count]);
      csvData.push(['视频时长(秒)', this.summary.video_duration.toFixed(2)]);
      csvData.push(['平均置信度', (this.summary.average_confidence * 100).toFixed(2) + '%']);
      csvData.push([]);
      csvData.push(['大小分布']);
      csvData.push(['小型煤块', this.summary.size_distribution.small]);
      csvData.push(['中型煤块', this.summary.size_distribution.medium]);
      csvData.push(['大型煤块', this.summary.size_distribution.large]);
      
      // 生成CSV内容
      let csvContent = csvData.map(row => row.join(',')).join('\n');
      
      // 创建Blob并下载
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      saveAs(blob, `煤块检测结果_${timestamp}.csv`);
      
      this.$message.success('CSV导出成功');
    },

    // 导出为Excel
    exportToExcel() {
      if (!this.detections || this.detections.length === 0) {
        this.$message.warning('没有可导出的数据');
        return;
      }
      
      // 如果未加载完整数据，先询问用户
      if (this.hasMoreDetections && !this.detailsLoaded) {
        this.$confirm('当前仅加载了部分数据，是否先加载完整数据再导出?', '提示', {
          confirmButtonText: '加载并导出',
          cancelButtonText: '仅导出当前数据',
          type: 'warning'
        }).then(() => {
          // 先加载完整数据
          this.loadFullDetails().then(() => {
            this.performExcelExport();
          });
        }).catch(() => {
          // 直接导出当前数据
          this.performExcelExport();
        });
      } else {
        // 已有完整数据，直接导出
        this.performExcelExport();
      }
    },

    performExcelExport() {
      // 创建工作簿
      const wb = XLSX.utils.book_new();
      
      // 准备主数据
      const mainData = [
        ['煤块ID', '置信度', '首次出现帧', '最后出现帧', '尺寸估计', '边界框坐标X1', '边界框坐标Y1', '边界框坐标X2', '边界框坐标Y2']
      ];
      
      this.detections.forEach(det => {
        mainData.push([
          det.track_id,
          (det.confidence * 100).toFixed(2) + '%',
          det.first_frame || 0,
          det.last_frame || 0,
          this.estimateSize(det.bbox),
          Math.round(det.bbox[0]),
          Math.round(det.bbox[1]),
          Math.round(det.bbox[2]),
          Math.round(det.bbox[3])
        ]);
      });
      
      // 创建主数据工作表
      const ws1 = XLSX.utils.aoa_to_sheet(mainData);
      XLSX.utils.book_append_sheet(wb, ws1, "煤块详情");
      
      // 创建汇总数据工作表
      const summaryData = [
        ['汇总信息', ''],
        ['总煤块数', this.summary.total_count],
        ['视频时长(秒)', this.summary.video_duration.toFixed(2)],
        ['平均置信度', (this.summary.average_confidence * 100).toFixed(2) + '%'],
        ['', ''],
        ['大小分布', ''],
        ['小型煤块', this.summary.size_distribution.small],
        ['中型煤块', this.summary.size_distribution.medium],
        ['大型煤块', this.summary.size_distribution.large],
        ['', ''],
        ['帧分布', '']
      ];
      
      // 添加帧分布数据
      Object.entries(this.summary.frame_distribution).forEach(([range, count]) => {
        summaryData.push([`${range} 帧`, count]);
      });
      
      const ws2 = XLSX.utils.aoa_to_sheet(summaryData);
      XLSX.utils.book_append_sheet(wb, ws2, "汇总信息");
      
      // 生成Excel文件
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const excelBuffer = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
      const blob = new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      saveAs(blob, `煤块检测结果_${timestamp}.xlsx`);
      
      this.$message.success('Excel导出成功');
    }
  }
}
</script>

<style scoped>
.video-detect-container {
  padding: 20px;
}

.upload-demo {
  margin: 20px 0;
}

.result-container {
  margin-top: 20px;
}

.result-video {
  max-width: 100%;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.detection-results {
  margin-top: 20px;
}

.loading {
  text-align: center;
  margin-top: 50px;
}

.task-status {
  margin-top: 10px;
  color: #409EFF;
  font-weight: bold;
}

.debug-info {
  background-color: #f8f8f8;
  border: 1px dashed #ddd;
  border-radius: 4px;
  padding: 10px;
  margin: 10px 0;
  font-size: 14px;
}

.debug-info code {
  display: block;
  overflow-x: auto;
  background-color: #f5f5f5;
  padding: 5px;
  border-radius: 3px;
  margin: 5px 0;
}

.fallback-player {
  margin-top: 20px;
  border-top: 1px solid #eee;
  padding-top: 15px;
}

.detection-summary {
  margin: 20px 0;
}

.summary-card {
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
  padding: 10px;
}

.stat-title {
  font-size: 14px;
  color: #909399;
  margin-bottom: 5px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #409EFF;
}

.size-chart {
  margin: 15px 0;
}

.size-bar {
  display: flex;
  height: 30px;
  border-radius: 4px;
  overflow: hidden;
}

.size-segment {
  display: flex;
  justify-content: center;
  align-items: center;
  color: white;
  padding: 0 10px;
  font-size: 12px;
  min-width: 60px;
}

.size-small {
  background-color: #67C23A;
}

.size-medium {
  background-color: #E6A23C;
}

.size-large {
  background-color: #F56C6C;
}

.frame-distribution {
  margin: 15px 0;
}

.frame-segment {
  margin-bottom: 10px;
}

.frame-label {
  font-size: 12px;
  color: #606266;
  margin-bottom: 5px;
}

.action-buttons {
  margin-top: 20px;
  text-align: center;
}

.detection-table {
  margin-top: 20px;
}

.detail-count {
  float: right;
  font-size: 14px;
  color: #909399;
}

.bbox-details {
  font-size: 12px;
  line-height: 1.5;
}

.bbox-details p {
  margin: 5px 0;
}

.more-data-hint {
  margin-top: 15px;
}

.pagination {
  margin-top: 15px;
  text-align: right;
}
</style>
