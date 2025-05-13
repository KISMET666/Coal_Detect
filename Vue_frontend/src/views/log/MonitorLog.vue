<template>
    <div class="monitor-log-container">
      <el-card class="log-card">
        <div slot="header">
          <h2>监控视频回放</h2>
          <div class="card-actions">
            <el-button type="primary" size="small" icon="el-icon-refresh" @click="fetchHistory">刷新列表</el-button>
            <el-button type="success" size="small" icon="el-icon-folder-opened" @click="openSaveFolder">打开文件夹</el-button>
          </div>
        </div>
        
        <div v-loading="loading">
          <!-- 没有记录的提示 -->
          <el-empty v-if="!historyData.length && !loading" description="暂无监控记录">
            <el-button type="primary" @click="goToMonitor">前往监控页面</el-button>
          </el-empty>
          
          <!-- 历史记录列表 -->
          <el-collapse v-if="historyData.length" v-model="activeDate">
            <el-collapse-item v-for="(dateItem, dateIndex) in historyData" :key="dateIndex" :name="dateIndex">
              <template slot="title">
                <div class="date-header">
                  <span class="date-label">{{ dateItem.date }}</span>
                  <el-tag type="info" size="small">{{ dateItem.videos.length }} 个视频</el-tag>
                  <el-tag v-if="dateItem.detection_count > 0" type="warning" size="small">
                    {{ dateItem.detection_count }} 个检测
                  </el-tag>
                </div>
              </template>
              
              <!-- 视频列表 -->
              <el-table
                :data="dateItem.videos"
                style="width: 100%"
                @row-click="openVideo"
              >
                <el-table-column
                  prop="filename"
                  label="视频文件"
                  min-width="200"
                >
                  <template slot-scope="scope">
                    <div class="video-name">
                      <i class="el-icon-video-camera"></i>
                      {{ getFormattedFilename(scope.row.filename) }}
                    </div>
                  </template>
                </el-table-column>
                
                <el-table-column
                  label="时间"
                  width="180"
                >
                  <template slot-scope="scope">
                    {{ formatTimestamp(scope.row.time) }}
                  </template>
                </el-table-column>
                
                <el-table-column
                  label="大小"
                  width="120"
                >
                  <template slot-scope="scope">
                    {{ formatFileSize(scope.row.size) }}
                  </template>
                </el-table-column>
                
                <el-table-column
                  label="检测结果"
                  width="120"
                  align="center"
                >
                  <template slot-scope="scope">
                    <el-tag 
                      v-if="scope.row.has_detections" 
                      type="success"
                      @click.stop="showDetections(dateItem.date, scope.row)"
                    >
                      {{ scope.row.detection_count || '查看' }}
                    </el-tag>
                    <span v-else>无</span>
                  </template>
                </el-table-column>
                
                <el-table-column
                  label="操作"
                  width="150"
                  align="center"
                >
                  <template slot-scope="scope">
                    <el-button 
                      type="text" 
                      icon="el-icon-video-play"
                      @click.stop="openVideo(scope.row)"
                    >播放</el-button>
                    
                  </template>
                </el-table-column>
              </el-table>
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-card>
      
      <!-- 视频播放对话框 -->
      <el-dialog
        title="视频回放"
        :visible.sync="videoDialogVisible"
        width="70%"
        :before-close="closeVideoDialog"
      >
        <div class="video-player-container">
          <!-- 调试信息区域 -->
        <!-- <div v-if="selectedVideo" class="debug-info">
          <p><strong>视频URL：</strong> <code>{{ selectedVideo.url }}</code></p>
          <p>
            <a :href="selectedVideo.url" target="_blank">直接访问视频</a> | 
            <el-button type="text" @click="validateVideo">验证视频</el-button>
          </p>
          <p v-if="videoErrorInfo"><strong>错误信息：</strong> {{ videoErrorInfo }}</p>
        </div> -->
        
        <!-- 主视频播放器 -->
          <video 
            v-if="selectedVideo" 
            ref="videoPlayer" 
            controls 
            class="video-player"
            :src="selectedVideo.url"
            @error="handleVideoError"
          ></video>
          <!-- 备用HTML5视频播放器 -->
        <div v-if="showFallbackPlayer" class="fallback-player">
          <h4>备用播放器</h4>
          <video 
            ref="fallbackPlayer"
            controls 
            class="video-player"
            @error="handleFallbackError"
          >
            <source :src="selectedVideo && selectedVideo.url" type="video/mp4">
            您的浏览器不支持视频播放
          </video>
        </div>
          
          <!-- 检测结果显示 -->
          <div v-if="selectedVideo && selectedVideo.has_detections && detectionResults.length" class="detection-panel">
            <h3>检测结果</h3>
            <el-table
              :data="detectionResults"
              height="300"
              stripe
              style="width: 100%"
            >
              <el-table-column
                label="序号"
                type="index"
                width="50"
              ></el-table-column>
              
              <el-table-column
                prop="class"
                label="类别"
                width="100"
              ></el-table-column>
              
              <el-table-column
                prop="confidence"
                label="置信度"
                width="100"
              >
                <template slot-scope="scope">
                  <el-tag :type="getConfidenceType(scope.row.confidence)">
                    {{ (scope.row.confidence * 100).toFixed(1) }}%
                  </el-tag>
                </template>
              </el-table-column>
              
              <el-table-column
               
                label="时间点"
                width="180"
              >
                <template slot-scope="scope">
                  {{ formatDetectionTimestamp(scope.row) }}
                  <el-button 
                    type="text" 
                    size="mini" 
                    icon="el-icon-video-play"
                    @click="seekToTimestamp(scope.row)"
                  >跳转</el-button>
                </template>
              </el-table-column>
              
              <el-table-column
                prop="bbox"
                label="位置"
              >
                <template slot-scope="scope">
                  [{{ scope.row.bbox.map(pos => Math.round(pos)).join(', ') }}]
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-dialog>
    </div>
  </template>
  
  <script>
  // import axios from 'axios';
  import { apiService } from '@/services/api';
  import dayjs from 'dayjs';
  import io from 'socket.io-client';
  
  export default {
    data() {
      return {
        loading: false,
        historyData: [],
        activeDate: [0], // 默认展开第一个日期
        selectedVideo: null,
        videoDialogVisible: false,
        detectionResults: [],
        socket: null,
        baseUrl: 'http://localhost:5000',
        showFallbackPlayer: false,
        videoErrorInfo: null,
        videoMetadata: null,  // 添加视频元数据变量
        uniqueCount: 0  // 添加唯一煤块计数变量
        }
    },
    mounted() {
      this.fetchHistory();
      this.initSocketConnection();
    },
    beforeDestroy() {
      if (this.socket) {
        this.socket.disconnect();
      }
    },
    methods: {
      initSocketConnection() {
        this.socket = io(this.baseUrl);
        
        this.socket.on('connect', () => {
          console.log('WebSocket connected');
        });
        
        this.socket.on('disconnect', () => {
          console.log('WebSocket disconnected');
        });
      },
      async fetchHistory() {
        this.loading = true;
        try {
          const response = await apiService.get(`/api/surveillance/history`);
          this.historyData = response.data;

          // 处理返回数据，确保URL是正确的
          if (this.historyData && this.historyData.length) {
            this.historyData.forEach(date => {
              if (date.videos && date.videos.length) {
                date.videos.forEach(video => {
                  // 确保URL使用的是正确的baseUrl
                  if (video.url && video.url.startsWith('/')) {
                    video.url = `${this.baseUrl}${video.url}`;
                  }
                });
              }
            });
          }
          
          // 如果没有活动的折叠项但有数据，则默认展开第一项
          if (this.activeDate.length === 0 && this.historyData.length > 0) {
            this.activeDate = [0];
          }
        } catch (error) {
          console.error('获取历史记录失败:', error);
          this.$message.error('获取历史记录失败: ' + (error.response?.data?.error || error.message));
        } finally {
          this.loading = false;
        }
      },
      formatTimestamp(timestamp) {
        return dayjs(timestamp * 1000).format('YYYY-MM-DD HH:mm:ss');
      },
      formatFileSize(size) {
        const kb = size / 1024;
        if (kb < 1024) {
          return kb.toFixed(2) + ' KB';
        } else {
          return (kb / 1024).toFixed(2) + ' MB';
        }
      },
      formatDetectionTimestamp(detection) {
        // 优先使用相对时间戳，因为它更适合视频播放定位
        if (detection.rel_timestamp !== undefined) {
          const minutes = Math.floor(detection.rel_timestamp / 60);
          const seconds = Math.floor(detection.rel_timestamp % 60);
          return `${minutes}:${seconds.toString().padStart(2, '0')}`;
        }
        
        // 如果有绝对时间戳，则使用它
        if (detection.abs_timestamp !== undefined) {
          return dayjs(detection.abs_timestamp * 1000).format('HH:mm:ss');
        }
        
        // 兼容旧数据，可能直接使用timestamp字段
        if (detection.timestamp !== undefined) {
          return dayjs(detection.timestamp * 1000).format('HH:mm:ss');
        }
        
        return "时间未知";
      },
      getFormattedFilename(filename) {
        // 从文件名中提取有意义的部分，如摄像头ID和时间
        const match = filename.match(/cam(\d+)_seg_(\d+-\d+-\d+)/);
        if (match) {
          return `摄像头 ${match[1]} - ${match[2].replace(/-/g, ':')}`;
        }
        return filename;
      },
      // 修改 openVideo 函数
      openVideo(row) {
        console.log('打开视频URL:', row.url);
        
        // 重置视频相关状态
        this.videoErrorInfo = null;
        this.showFallbackPlayer = false;
        
        this.selectedVideo = row;
        
        // 准备视频URL
        if (this.selectedVideo && this.selectedVideo.url) {
          // 如果是相对路径，添加基础URL
          if (!this.selectedVideo.url.startsWith('http')) {
            this.selectedVideo.url = `${this.baseUrl}${this.selectedVideo.url}`;
          }
          
          // 获取认证token
          const token = localStorage.getItem('token');
          
          // 构建完整URL，包含token和时间戳
          const urlWithParams = new URL(this.selectedVideo.url);
          urlWithParams.searchParams.append('token', token);
          urlWithParams.searchParams.append('t', Date.now());
          
          this.selectedVideo.url = urlWithParams.toString();
          console.log('完整视频URL:', this.selectedVideo.url);
        }
        
        this.videoDialogVisible = true;
        
        // 如果有检测结果，加载它们
        if (row.has_detections) {
          this.loadDetectionResults(row);
        } else {
          this.detectionResults = [];
        }
        
        // 先通过Fetch检查视频是否可以获取
        this.checkAndPrepareVideo();
      },

      // 新增：检查并准备视频
      checkAndPrepareVideo() {
        if (!this.selectedVideo || !this.selectedVideo.url) return;
        
        this.$message.info('正在准备视频播放...');
        
        // 获取认证token
        const token = localStorage.getItem('token');
        
        // 先用fetch检查URL是否可访问
        fetch(this.selectedVideo.url, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })
        .then(response => {
          if (!response.ok) {
            throw new Error(`HTTP错误! 状态码: ${response.status}`);
          }
          
          console.log('视频请求成功，正在处理响应...');
          return response.blob();
        })
        .then(blob => {
          console.log(`接收到视频数据，大小: ${(blob.size/1024/1024).toFixed(2)}MB`);
          
          // 创建Blob URL
          const blobUrl = URL.createObjectURL(blob);
          console.log('已创建Blob URL:', blobUrl);
          
          // 设置到主播放器
          this.$nextTick(() => {
            if (this.$refs.videoPlayer) {
              this.$refs.videoPlayer.src = blobUrl;
              this.$refs.videoPlayer.load();
              
              // 设置事件处理
              this.$refs.videoPlayer.oncanplay = () => {
                console.log('主播放器准备就绪，开始播放');
                this.$refs.videoPlayer.play()
                  .then(() => {
                    this.$message.success('视频加载成功!');
                    this.showFallbackPlayer = false; // 确保备用播放器隐藏
                  })
                  .catch(e => {
                    console.error('主播放器播放失败:', e);
                    this.activateFallbackPlayer(blobUrl);
                  });
              };
              
              this.$refs.videoPlayer.onerror = (err) => {
                console.error('主播放器加载错误:', err);
                this.videoErrorInfo = '视频格式不受支持，正在尝试备用播放器';
                this.activateFallbackPlayer(blobUrl);
              };
              this.$refs.videoPlayer.onloadedmetadata = () => {
                console.log(`视频元数据加载完成，时长: ${this.$refs.videoPlayer.duration}秒，尺寸: ${this.$refs.videoPlayer.videoWidth}x${this.$refs.videoPlayer.videoHeight}`);
                
                // 检查视频时长与元数据是否匹配
                if (this.videoMetadata && this.videoMetadata.duration > 0) {
                  const durationDiff = Math.abs(this.$refs.videoPlayer.duration - this.videoMetadata.duration);
                  if (durationDiff > 5) { // 如果差异超过5秒
                    console.warn(`警告：视频时长(${this.$refs.videoPlayer.duration}秒)与元数据记录(${this.videoMetadata.duration}秒)不匹配`);
                  }
                }
              };

              this.$refs.videoPlayer.ontimeupdate = () => {
              // 每秒只记录一次以减少日志量
              if (Math.floor(this.$refs.videoPlayer.currentTime) % 5 === 0) {
                console.log(`当前播放位置: ${this.$refs.videoPlayer.currentTime.toFixed(2)}秒`);
              }
            };
            }
          });
        })
        .catch(error => {
          console.error('无法加载视频:', error);
          this.$message.error(`无法加载视频: ${error.message}`);
          this.videoErrorInfo = `加载错误: ${error.message}`;
        });
      },

      // 新增：激活备用播放器
      activateFallbackPlayer(blobUrl) {
        this.showFallbackPlayer = true;
        this.$message.info('正在尝试使用备用播放器...');
        
        this.$nextTick(() => {
          if (this.$refs.fallbackPlayer) {
            this.$refs.fallbackPlayer.src = blobUrl;
            this.$refs.fallbackPlayer.load();
            
            this.$refs.fallbackPlayer.oncanplay = () => {
              console.log('备用播放器准备就绪，开始播放');
              this.$refs.fallbackPlayer.play()
                .then(() => this.$message.success('备用播放器加载成功!'))
                .catch(e => console.error('备用播放器播放失败:', e));
            };
            
            this.$refs.fallbackPlayer.onerror = (err) => {
              console.error('备用播放器也失败了:', err);
              this.videoErrorInfo += ' | 备用播放器也失败';
              this.$message.error('视频无法播放，请检查格式或下载后播放');
            };
          }
        });
      },

      // 修改 handleVideoError 函数
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
        
        // 如果主播放器失败，但还没有尝试过检查和准备视频
        // 那么调用检查和准备视频的方法
        this.checkAndPrepareVideo();
      },
      
      // 备用播放器错误处理
      handleFallbackError(event) {
        console.error('备用播放器也失败了:', event);
        this.videoErrorInfo += ' | 备用播放器也失败';
        this.$message.error('备用播放器也失败了，请检查视频格式和服务器配置');
      },
      
      // 验证视频URL是否可访问
      validateVideo() {
        if (!this.selectedVideo || !this.selectedVideo.url) return;
        
        console.log('正在验证视频URL:', this.selectedVideo.url);
        
        // 检查当前视频元素状态
        const videoElement = this.$refs.videoPlayer;
        if (videoElement) {
          console.log('视频元素网络状态:', videoElement.networkState);
          console.log('视频元素准备状态:', videoElement.readyState);
          console.log('视频元素错误对象:', videoElement.error);
        }
        
        // 测试通过XHR直接获取视频
        this.$message.info('正在测试视频URL可访问性...');
        apiService.get(this.selectedVideo.url, { responseType: 'blob' })
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
      closeVideoDialog() {
        // 暂停视频播放
        if (this.$refs.videoPlayer) {
          this.$refs.videoPlayer.pause();
        }
        this.videoDialogVisible = false;
      },
      async loadDetectionResults(video) {
        const date = this.historyData.find(d => d.videos.includes(video))?.date;
        if (!date) {
          this.$message.error('无法确定视频日期');
          return;
        }
        
        try {
          const response = await apiService.get(`/api/surveillance/detection/${date}/${video.filename}`);
          
          // 如果有唯一煤块数据，优先使用
          if (response.data.unique_detections) {
            this.detectionResults = response.data.unique_detections;
            this.uniqueCount = response.data.unique_count || this.detectionResults.length;
          } else if (response.data.detections){
            this.detectionResults = response.data.detections || [];
            this.uniqueCount = response.data.unique_count || 0;
          } else {
            // 如果没有任何检测结果
            this.detectionResults = [];
            this.uniqueCount = 0;
            throw new Error('返回数据中没有检测结果');
          }
          // 保存视频元数据
          this.videoMetadata = response.data.video_metadata || {
            start_time: video.time,
            duration: 0,
            fps: 30
          };
          // 检查并修复数据中的时间戳
          this.detectionResults = this.detectionResults.map(detection => {
            // 创建一个新对象以避免修改原对象
            const updatedDetection = { ...detection };
            
            // 如果缺少相对时间戳但有绝对时间戳，计算相对时间戳
            if (updatedDetection.rel_timestamp === undefined && 
                updatedDetection.abs_timestamp !== undefined && 
                this.videoMetadata.start_time) {
              updatedDetection.rel_timestamp = updatedDetection.abs_timestamp - this.videoMetadata.start_time;
            }
            
            // 如果缺少绝对时间戳但有相对时间戳，计算绝对时间戳
            if (updatedDetection.abs_timestamp === undefined && 
                updatedDetection.rel_timestamp !== undefined && 
                this.videoMetadata.start_time) {
              updatedDetection.abs_timestamp = this.videoMetadata.start_time + updatedDetection.rel_timestamp;
            }
            
            // 向后兼容：如果只有老式的timestamp字段，尝试将其转换为abs_timestamp和rel_timestamp
            if (updatedDetection.timestamp !== undefined && 
                updatedDetection.abs_timestamp === undefined) {
              // 把timestamp当作绝对时间戳
              updatedDetection.abs_timestamp = updatedDetection.timestamp;
              
              // 如果可能，计算相对时间戳
              if (this.videoMetadata.start_time) {
                updatedDetection.rel_timestamp = updatedDetection.timestamp - this.videoMetadata.start_time;
              }
            }
            
            return updatedDetection;
          });
          
          // 提供调试信息
          console.log('视频元数据:', this.videoMetadata);
          console.log('处理后的首个检测结果:', this.detectionResults[0]);
          
          // 检查数据是否有效
          if (this.detectionResults.length > 0) {
            // 确保有显示用的时间戳，检查至少一种格式的时间戳存在
            const hasValidTimestamps = this.detectionResults.every(det => 
              det.rel_timestamp !== undefined || 
              det.abs_timestamp !== undefined || 
              det.timestamp !== undefined);
            
            if (!hasValidTimestamps) {
              console.warn('警告：部分检测结果缺少有效时间戳');
            }
            
            // 更新UI
            this.$message.success(`成功加载了 ${this.uniqueCount} 个唯一煤块`);
          } else {
            this.$message.info('没有检测到煤块');
          }
        } catch (error) {
          console.error('获取检测结果失败:', error);
          this.$message.error('加载检测结果失败: ' + (error.response?.data?.error || error.message));
          this.detectionResults = [];
          this.uniqueCount = 0;
        }
      },
      showDetections(date, video) {
        this.selectedVideo = video;
        this.loadDetectionResults(video);
        this.videoDialogVisible = true;
      },
      getConfidenceType(confidence) {
        const percent = confidence * 100;
        if (percent >= 80) return 'success';
        if (percent >= 60) return 'warning';
        return 'danger';
      },
      
      seekToTimestamp(detection) {
        // 如果视频播放器不存在，直接返回
        if (!this.$refs.videoPlayer) return;
        
        // 使用相对时间戳直接跳转（优先级最高）
        if (detection.rel_timestamp !== undefined) {
          console.log(`跳转到相对时间: ${detection.rel_timestamp}秒`);
          this.$refs.videoPlayer.currentTime = detection.rel_timestamp;
          this.$refs.videoPlayer.play();
          return;
        }
        
        // 处理绝对时间戳（第二优先级）
        if (detection.abs_timestamp !== undefined) {
          // 获取视频开始时间，首先从视频元数据中获取，如果不存在则从视频对象获取
          const videoStartTime = this.videoMetadata?.start_time || 
            (typeof this.selectedVideo.time === 'number' ? 
              this.selectedVideo.time : 
              (new Date(this.selectedVideo.time)).getTime() / 1000);
              
          // 计算相对时间点
          const seekTime = detection.abs_timestamp - videoStartTime;
          console.log(`跳转：视频开始=${videoStartTime}, 目标=${detection.abs_timestamp}, 相对=${seekTime}秒`);
          
          if (seekTime >= 0) {
            this.$refs.videoPlayer.currentTime = seekTime;
            this.$refs.videoPlayer.play();
          } else {
            this.$message.warning(`无法跳转：目标时间点早于视频开始时间 ${seekTime.toFixed(2)}秒`);
            this.$refs.videoPlayer.currentTime = 0;
            this.$refs.videoPlayer.play();
          }
          return;
        }
        
        // 兼容旧数据格式中的 timestamp 字段（最低优先级）
        if (detection.timestamp !== undefined) {
          // 获取视频开始时间
          const videoStartTime = this.videoMetadata?.start_time || 
            (typeof this.selectedVideo.time === 'number' ? 
              this.selectedVideo.time : 
              (new Date(this.selectedVideo.time)).getTime() / 1000);
              
          // 确保 timestamp 是数值类型
          const targetTimestamp = typeof detection.timestamp === 'number' ? 
                                detection.timestamp : 
                                (new Date(detection.timestamp)).getTime() / 1000;
              
          // 计算相对时间点
          const seekTime = targetTimestamp - videoStartTime;
          console.log(`兼容模式跳转：视频开始=${videoStartTime}, 目标=${targetTimestamp}, 相对=${seekTime}秒`);
          
          if (seekTime >= 0) {
            this.$refs.videoPlayer.currentTime = seekTime;
            this.$refs.videoPlayer.play();
          } else {
            this.$message.warning(`无法跳转：目标时间点早于视频开始时间 ${seekTime.toFixed(2)}秒`);
            this.$refs.videoPlayer.currentTime = 0;
            this.$refs.videoPlayer.play();
          }
          return;
        }
        
        // 如果没有任何可用的时间戳信息
        this.$message.warning('无法跳转：缺少时间戳信息');
        this.$refs.videoPlayer.currentTime = 0;
        this.$refs.videoPlayer.play();
      },

      openSaveFolder() {
        if (this.socket) {
          this.socket.emit('open_save_folder', { path: 'D:\\SurveillanceVideo' });
          this.$message.success('正在打开监控视频文件夹');
        }
      },
      goToMonitor() {
        this.$router.push('/Monitor');
      }
    }
  }
  </script>
  
  <style scoped>
  .monitor-log-container {
    padding: 20px;
  }
  
  .log-card {
    margin-bottom: 20px;
  }
  
  .log-card >>> .el-card__header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .log-card >>> .el-card__header h2 {
    margin: 0;
  }
  
  .card-actions {
    display: flex;
    gap: 10px;
  }
  
  .date-header {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  
  .date-label {
    font-weight: bold;
    font-size: 16px;
  }
  
  .video-name {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  
  .video-player-container {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  
  .video-player {
    width: 100%;
    max-height: 600px;
    border-radius: 4px;
    outline: none;
  }
  
  .detection-panel {
    border-top: 1px solid #ebeef5;
    padding-top: 20px;
  }
  
  .detection-panel h3 {
    margin-top: 0;
    margin-bottom: 15px;
    color: #606266;
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
  </style>