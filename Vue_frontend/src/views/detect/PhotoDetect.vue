<template>
  <div class="photo-detect-container">
    <el-card class="box-card">
      <div slot="header" class="clearfix">
        <h2 style="margin: 0">煤块图片检测</h2>
      </div>

      <!-- 上传区域 -->
      <el-upload
        class="upload-area"
        drag
        action=""
        :auto-upload="false"
        :on-change="handleImageUpload"
        :show-file-list="false"
        :before-upload="beforeImageUpload"
        accept="image/*"
      >
        <i class="el-icon-upload"></i>
        <div class="el-upload__text">
          将图片拖到此处，或<em>点击选择</em>
          <div class="el-upload__tip" slot="tip">
            支持 JPG/PNG 格式，大小不超过 10MB
          </div>
        </div>
      </el-upload>

      <!-- 检测结果展示 -->
      <div v-if="resultState !== 'empty'" class="result-section">
        <el-divider content-position="left">检测结果</el-divider>
        
        <!-- 状态提示 -->
        <div v-if="resultState === 'loading'" class="loading-state">
          <el-progress type="circle" :percentage="progressPercent"></el-progress>
          <p class="loading-text">正在分析图片中... {{ progressPercent }}%</p>
        </div>

        <!-- 错误状态 -->
        <div v-if="resultState === 'error'" class="error-state">
          <el-alert
            title="检测失败"
            type="error"
            :description="errorMessage"
            show-icon
            closable
          ></el-alert>
          <el-button 
            type="primary" 
            @click="retryDetection"
            class="retry-button"
          >
            重新尝试
          </el-button>
        </div>

        <!-- 检测成功 -->
        <div v-if="resultState === 'success'" class="success-result">
          <div class="image-container">
            <el-image 
              :src="resultImageUrl.replace('http://localhost:7000','http://127.0.0.1:5000')" 
              :preview-src-list="[resultImageUrl.replace('http://localhost:7000','http://127.0.0.1:5000')]"
              fit="contain"
              class="result-image"
            >
              <div slot="error" class="image-error">
                <i class="el-icon-picture-outline"></i>
                <p>图片加载失败</p>
              </div>
            </el-image>
          </div>

          <!-- 检测数据统计 -->
          <div class="stats-panel">
            <el-card shadow="never">
              <div slot="header" class="stats-header">
                <span>检测统计</span>
                <el-tag type="success" effect="dark">
                  煤块数量: {{ detectionData.length }}
                </el-tag>
              </div>
              <div class="stats-content">
                <div class="stat-item">
                  <span class="stat-label">平均置信度:</span>
                  <el-progress 
                    :percentage="averageConfidence" 
                    :color="confidenceColor"
                    :format="formatConfidence"
                  ></el-progress>
                </div>
                <div class="stat-item">
                  <span class="stat-label">检测耗时:</span>
                  <span class="stat-value">{{ detectionTime }} 秒</span>
                </div>
              </div>
            </el-card>
          </div>

          <!-- 检测结果表格 -->
          <div class="detection-table">
            <el-table
              :data="detectionData"
              border
              style="width: 100%"
              height="300"
              v-loading="tableLoading"
            >
              <el-table-column
                prop="id"
                label="序号"
                width="80"
                align="center"
              >
                <template #default="{ $index }">
                  {{ $index + 1 }}
                </template>
              </el-table-column>
              <el-table-column
                prop="class"
                label="类别"
                width="120"
                align="center"
              ></el-table-column>
              <el-table-column
                prop="confidence"
                label="置信度"
                width="150"
                align="center"
              >
                <template #default="{ row }">
                  <el-tag :type="getConfidenceTagType(row.confidence)">
                    {{ (row.confidence * 100).toFixed(2) }}%
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column
                prop="bbox"
                label="位置坐标"
                align="center"
              >
                <template #default="{ row }">
                  <el-popover
                    placement="top-start"
                    width="200"
                    trigger="hover"
                  >
                    <div class="bbox-detail">
                      <p>左上: ({{ row.bbox[0].toFixed(2) }}, {{ row.bbox[1].toFixed(2) }})</p>
                      <p>右下: ({{ row.bbox[2].toFixed(2) }}, {{ row.bbox[3].toFixed(2) }})</p>
                      <p>宽度: {{ (row.bbox[2] - row.bbox[0]).toFixed(2) }}</p>
                      <p>高度: {{ (row.bbox[3] - row.bbox[1]).toFixed(2) }}</p>
                    </div>
                    <el-button slot="reference" type="text">
                      {{ row.bbox.slice(0, 2).map(x => x.toFixed(0)).join(',') }} - 
                      {{ row.bbox.slice(2).map(x => x.toFixed(0)).join(',') }}
                    </el-button>
                  </el-popover>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script>
import { apiService } from '@/services/api';
import axios from 'axios';

export default {
  name: 'PhotoDetect',
  data() {
    return {
      resultState: 'empty', // empty | loading | success | error
      progressPercent: 0,
      resultImageUrl: '',
      detectionData: [],
      detectionTime: 0,
      errorMessage: '',
      tableLoading: false,
      uploadFile: null
    };
  },
  computed: {
    averageConfidence() {
      if (this.detectionData.length === 0) return 0;
      const sum = this.detectionData.reduce((acc, item) => acc + item.confidence, 0);
      return Math.round((sum / this.detectionData.length) * 100);
    },
    confidenceColor() {
      if (this.averageConfidence >= 80) return '#67C23A';
      if (this.averageConfidence >= 60) return '#E6A23C';
      return '#F56C6C';
    }
  },
  methods: {
    beforeImageUpload(file) {
      const isImage = file.type.startsWith('image/');
      const isLt10M = file.size / 1024 / 1024 < 10;
      
      if (!isImage) {
        this.$message.error('只能上传图片文件!');
      }
      if (!isLt10M) {
        this.$message.error('图片大小不能超过 10MB!');
      }
      
      return isImage && isLt10M;
    },
    
    handleImageUpload(file) {
      this.uploadFile = file;
      this.startDetection();
    },
    
    async startDetection() {
      this.resultState = 'loading';
      this.progressPercent = 0;
      this.errorMessage = '';
      
      const formData = new FormData();
      formData.append('file', this.uploadFile.raw);
      
      try {
        const startTime = Date.now();
        
        const response = await apiService.post('/api/detect/image', formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          },
          onUploadProgress: (progressEvent) => {
            this.progressPercent = Math.min(
              99,
              Math.round((progressEvent.loaded * 100) / progressEvent.total)
            );
          }
        });
        console.log('检测响应:', response.data);  // 查看原始响应
        console.log('完整图片URL:', 'http://127.0.0.1:5000' + response.data.result_url);  // 打印完整URL
        
        this.detectionTime = ((Date.now() - startTime) / 1000).toFixed(2);
        // 替换原有的resultImageUrl赋值
        this.resultImageUrl = `http://localhost:5000${response.data.result_url}?t=${Date.now()}`;
        this.detectionData = response.data.detections;
        this.resultState = 'success';
        this.progressPercent = 100;
        
        this.$message.success('检测完成!');
      } catch (error) {
        console.error('Detection error:', error);
        this.resultState = 'error';
        this.errorMessage = error.response?.data?.error || 
                           error.message || 
                           '未知错误，请检查网络连接或服务状态';
        this.$message.error('检测失败: ' + this.errorMessage);
      }
    },
    
    retryDetection() {
      if (this.uploadFile) {
        this.startDetection();
      }
    },
    
    formatConfidence(percentage) {
      return `置信度: ${percentage}%`;
    },
    
    getConfidenceTagType(confidence) {
      const percent = confidence * 100;
      if (percent >= 80) return 'success';
      if (percent >= 60) return 'warning';
      return 'danger';
    }
  }
};
</script>

<style scoped>
.photo-detect-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.upload-area {
  margin-bottom: 30px;
}

.result-section {
  margin-top: 30px;
}

.loading-state {
  text-align: center;
  padding: 40px 0;
}

.loading-text {
  margin-top: 15px;
  font-size: 16px;
  color: #606266;
}

.error-state {
  text-align: center;
  padding: 20px;
}

.retry-button {
  margin-top: 20px;
}

.success-result {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.image-container {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px;
  background-color: #f5f7fa;
}

.result-image {
  width: 100%;
  max-height: 500px;
  display: block;
  margin: 0 auto;
}

.image-error {
  height: 200px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #909399;
}

.image-error i {
  font-size: 50px;
  margin-bottom: 10px;
}

.stats-panel {
  margin-top: 20px;
}

.stats-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stats-content {
  padding: 10px;
}

.stat-item {
  margin-bottom: 15px;
}

.stat-label {
  display: inline-block;
  width: 100px;
  font-weight: bold;
}

.stat-value {
  margin-left: 10px;
}

.detection-table {
  margin-top: 20px;
}

.bbox-detail p {
  margin: 5px 0;
  font-size: 12px;
}
</style>