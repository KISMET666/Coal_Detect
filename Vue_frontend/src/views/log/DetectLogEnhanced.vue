<template>
  <div class="detect-log-container">
    <!-- 顶部导航与过滤器 -->
    <el-card class="filter-card">
      <div slot="header" class="card-header">
        <el-tabs v-model="activeTab" @tab-click="handleTabChange">
          <el-tab-pane label="仪表盘" name="dashboard"></el-tab-pane>
          <el-tab-pane label="检测记录" name="records"></el-tab-pane>
          <el-tab-pane label="对比分析" name="comparison"></el-tab-pane>
        </el-tabs>
        <div class="header-actions">
          <el-button type="primary" size="small" icon="el-icon-refresh" @click="refreshData">刷新</el-button>
          <el-button type="success" size="small" icon="el-icon-download" @click="showExportOptions">导出</el-button>
        </div>
      </div>
      
      <!-- 高级过滤面板 -->
      <div class="advanced-filter">
        <el-form :inline="true" :model="filterForm" size="small">
          <el-form-item label="时间范围">
            <el-date-picker
              v-model="filterForm.dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="yyyy-MM-dd"
              :picker-options="pickerOptions"
              :clearable="false"
            ></el-date-picker>
          </el-form-item>
          
          <el-form-item label="摄像头">
            <el-select 
              v-model="filterForm.cameraIds" 
              multiple 
              collapse-tags
              placeholder="选择摄像头"
              @change="onCameraSelectChange">
              <el-option 
                v-for="i in 9" 
                :key="i" 
                :label="`摄像头 ${i}${!hasCameraData('cam'+(i-1)) ? ' (未接入)' : ''}`" 
                :value="`cam${i-1}`"
              ></el-option>
            </el-select>
          </el-form-item>
          
          <el-form-item label="置信度">
            <el-slider
              v-model="filterForm.confidenceRange"
              range
              :min="0"
              :max="100"
              :format-tooltip="formatConfidence"
              :step="1"
              style="width: 220px; margin-top: 8px;"
            ></el-slider>
          </el-form-item>
          <br>
          <el-form-item>
            <el-button type="primary" @click="applyFilters">应用筛选</el-button>
            <el-button @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>
        
      </div>
      
      <!-- 数据统计摘要 -->
      <div class="stats-summary" v-if="activeTab === 'dashboard' || activeTab === 'records'">
        <el-row :gutter="20">
          <el-col :span="6">
            <stat-card
              title="总检测数量"
              :value="statistics.totalCount"
              icon="el-icon-data-analysis"
              color="#409EFF"
            ></stat-card>
          </el-col>
          <el-col :span="6">
            <stat-card
              title="唯一煤块数"
              :value="statistics.uniqueCount"
              icon="el-icon-view"
              color="#67C23A"
            ></stat-card>
          </el-col>
          <el-col :span="6">
            <stat-card
              title="平均置信度"
              :value="`${statistics.avgConfidence.toFixed(1)}%`"
              icon="el-icon-success"
              color="#E6A23C"
            ></stat-card>
          </el-col>
          <el-col :span="6">
            <stat-card
              title="检测视频数"
              :value="statistics.videoCount"
              icon="el-icon-video-camera"
              color="#F56C6C"
            ></stat-card>
          </el-col>
        </el-row>
      </div>
    </el-card>
    
    <!-- 仪表盘视图 -->
    <div v-if="activeTab === 'dashboard'">
      <el-row :gutter="20" class="dashboard-row">
        <!-- 煤块检测趋势图 -->
        <el-col :span="16">
          <el-card class="chart-card">
            <div slot="header">
              <span>煤块检测趋势</span>
              <el-radio-group v-model="trendTimeRange" size="mini" @change="updateTrendChart">
                <el-radio-button label="day">日</el-radio-button>
                <el-radio-button label="week">周</el-radio-button>
                <el-radio-button label="month">月</el-radio-button>
              </el-radio-group>
            </div>
            <div id="trendChart" class="chart"></div>
          </el-card>
        </el-col>
        
        <!-- 煤块尺寸分布 -->
        <el-col :span="8">
          <el-card class="chart-card">
            <div slot="header">煤块尺寸分布</div>
            <div id="sizeDistributionChart" class="chart pie-chart"></div>
          </el-card>
        </el-col>
      </el-row>
      
      <el-row :gutter="20" class="dashboard-row">
        <!-- 摄像头检测分布 -->
        <el-col :span="12">
          <el-card class="chart-card">
            <div slot="header">摄像头检测分布</div>
            <div id="cameraDistributionChart" class="chart"></div>
          </el-card>
        </el-col>
        
        <!-- 置信度分布 -->
        <el-col :span="12">
          <el-card class="chart-card">
            <div slot="header">置信度分布</div>
            <div id="confidenceDistributionChart" class="chart"></div>
          </el-card>
        </el-col>
      </el-row>
      
      <!-- 检测时间热力图 -->
      <el-row class="dashboard-row">
        <el-col :span="24">
          <el-card class="chart-card">
            <div slot="header">检测时间分布热图</div>
            <div id="timeHeatmapChart" class="chart heatmap-chart"></div>
          </el-card>
        </el-col>
      </el-row>
      
      <!-- 异常检测面板 -->
      <el-row class="dashboard-row" v-if="anomalies.length > 0">
        <el-col :span="24">
          <el-card class="anomaly-card">
            <div slot="header">
              <span>异常检测</span>
              <el-tag type="danger">{{ anomalies.length }}个异常</el-tag>
            </div>
            <el-timeline>
              <el-timeline-item
                v-for="(anomaly, index) in anomalies"
                :key="index"
                :type="anomaly.level === 'high' ? 'danger' : 'warning'"
                :timestamp="formatTimestamp(anomaly.timestamp)"
              >
                <div class="anomaly-item">
                  <h4>{{ anomaly.title }}</h4>
                  <p>{{ anomaly.description }}</p>
                  <el-button 
                    type="text" 
                    size="mini" 
                    @click="showLogDetail(anomaly.source)"
                  >查看详情</el-button>
                </div>
              </el-timeline-item>
            </el-timeline>
          </el-card>
        </el-col>
      </el-row>
    </div>
    
    <!-- 检测记录表格视图 -->
    <div v-if="activeTab === 'records'">
      <el-card>
        <div slot="header">
          <span>检测记录列表</span>
          <div class="table-actions">
            <el-input
              placeholder="搜索..."
              v-model="searchQuery"
              size="small"
              prefix-icon="el-icon-search"
              @input="handleSearch"
              style="width: 200px; margin-right: 10px;"
            ></el-input>
            <el-select v-model="sortOption" size="small" @change="handleSortChange">
              <el-option label="时间↓" value="time_desc"></el-option>
              <el-option label="时间↑" value="time_asc"></el-option>
              <el-option label="检测数量↓" value="count_desc"></el-option>
              <el-option label="置信度↓" value="confidence_desc"></el-option>
            </el-select>
          </div>
        </div>
        
        <el-table
          :data="paginatedLogs"
          style="width: 100%"
          @row-click="showLogDetail"
          border
          stripe
          :row-class-name="getRowClass"
          v-loading="loading"
        >
          <el-table-column type="expand">
            <template slot-scope="props">
              <el-row class="expanded-row">
                <el-col :span="12">
                  <h4>检测统计</h4>
                  <el-descriptions :column="2" border size="small">
                    <el-descriptions-item label="唯一煤块">
                      <el-tag size="small">{{ getUniqueCount(props.row) }}</el-tag>
                    </el-descriptions-item>
                    <el-descriptions-item label="小型煤块">
                      {{ getSizeCount(props.row, 'small') }}
                    </el-descriptions-item>
                    <el-descriptions-item label="中型煤块">
                      {{ getSizeCount(props.row, 'medium') }}
                    </el-descriptions-item>
                    <el-descriptions-item label="大型煤块">
                      {{ getSizeCount(props.row, 'large') }}
                    </el-descriptions-item>
                    <el-descriptions-item label="平均置信度">
                      <el-progress
                        :percentage="getAvgConfidence(props.row)"
                        :status="getConfidenceStatus(getAvgConfidence(props.row))"
                      ></el-progress>
                    </el-descriptions-item>
                  </el-descriptions>
                </el-col>
                <el-col :span="12">
                  <h4>视频信息</h4>
                  <div class="video-thumbnail">
                    <div class="thumbnail-placeholder">
                      <i class="el-icon-video-camera"></i>
                      <span>{{ props.row.filename }}</span>
                    </div>
                    <el-button 
                      type="primary" 
                      size="small" 
                      icon="el-icon-video-play"
                      @click.stop="playVideo(props.row)"
                    >播放视频</el-button>
                  </div>
                </el-col>
              </el-row>
            </template>
          </el-table-column>
          
          <el-table-column
            prop="date"
            label="日期"
            width="120"
            sortable
          ></el-table-column>
          
          <el-table-column
            label="时间"
            width="180"
            sortable
          >
            <template slot-scope="scope">
              {{ formatTimestamp(scope.row.timestamp) }}
            </template>
          </el-table-column>
          
          <el-table-column
            label="摄像头"
            width="110"
          >
            <template slot-scope="scope">
              <el-tag type="primary" size="medium">
                {{ formatCameraId(scope.row.camera_id) }}
              </el-tag>
            </template>
          </el-table-column>
          
          <el-table-column
            label="检测数量"
            width="100"
            align="center"
            sortable
          >
            <template slot-scope="scope">
              <el-badge :value="scope.row.detection_count || 0" :max="99" type="primary">
                <i class="el-icon-aim"></i>
              </el-badge>
            </template>
          </el-table-column>
          
          <el-table-column
            label="置信度"
            width="150"
          >
            <template slot-scope="scope">
              <el-progress
                :percentage="getAvgConfidence(scope.row)"
                :status="getConfidenceStatus(getAvgConfidence(scope.row))"
              ></el-progress>
            </template>
          </el-table-column>
          
          <el-table-column
            label="煤块尺寸分布"
            min-width="180"
          >
            <template slot-scope="scope">
              <div class="size-distribution">
                <el-tooltip content="小型煤块" placement="top">
                  <div class="size-bar">
                    <div 
                      class="size-segment size-small" 
                      :style="{width: getSizePercentage(scope.row, 'small') + '%'}"
                    >
                      {{ getSizeCount(scope.row, 'small') }}
                    </div>
                  </div>
                </el-tooltip>
                <el-tooltip content="中型煤块" placement="top">
                  <div class="size-bar">
                    <div 
                      class="size-segment size-medium" 
                      :style="{width: getSizePercentage(scope.row, 'medium') + '%'}"
                    >
                      {{ getSizeCount(scope.row, 'medium') }}
                    </div>
                  </div>
                </el-tooltip>
                <el-tooltip content="大型煤块" placement="top">
                  <div class="size-bar">
                    <div 
                      class="size-segment size-large" 
                      :style="{width: getSizePercentage(scope.row, 'large') + '%'}"
                    >
                      {{ getSizeCount(scope.row, 'large') }}
                    </div>
                  </div>
                </el-tooltip>
              </div>
            </template>
          </el-table-column>
          
          <el-table-column
            label="操作"
            width="150"
            align="center"
            fixed="right"
          >
            <template slot-scope="scope">
              <el-button 
                type="text" 
                icon="el-icon-view"
                @click.stop="showLogDetail(scope.row)"
              >详情</el-button>
              
            </template>
          </el-table-column>
        </el-table>
        
        <!-- 分页控件 -->
        <div class="pagination" v-if="filteredLogs.length > 0">
          <el-pagination
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
            :current-page="currentPage"
            :page-sizes="[10, 20, 50, 100]"
            :page-size="pageSize"
            layout="total, sizes, prev, pager, next, jumper"
            :total="filteredLogs.length">
          </el-pagination>
        </div>
      </el-card>
    </div>
    
    <!-- 对比分析视图 -->
    <div v-if="activeTab === 'comparison'">
      <el-card>
        <div slot="header">
          <span>对比分析</span>
        </div>
        
        <div class="comparison-settings">
          <el-alert
            title="选择两个时间段或摄像头进行对比分析"
            type="info"
            :closable="false"
            show-icon
          ></el-alert>
          
          <el-divider content-position="left">对比设置</el-divider>
          
          <el-form :inline="true" size="small">
            <el-form-item label="对比类型">
              <el-radio-group v-model="comparisonSettings.type">
                <el-radio-button label="time">时间段对比</el-radio-button>
                <el-radio-button label="camera">摄像头对比</el-radio-button>
              </el-radio-group>
            </el-form-item>
            
            <template v-if="comparisonSettings.type === 'time'">
              <el-form-item label="时间段A">
                <el-date-picker
                  v-model="comparisonSettings.timeA"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  value-format="yyyy-MM-dd"
                ></el-date-picker>
              </el-form-item>
              
              <el-form-item label="时间段B">
                <el-date-picker
                  v-model="comparisonSettings.timeB"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  value-format="yyyy-MM-dd"
                ></el-date-picker>
              </el-form-item>
              
              <el-form-item label="摄像头">
                <el-select 
                  v-model="comparisonSettings.cameraIds" 
                  multiple 
                  collapse-tags
                  placeholder="选择摄像头">
                  <el-option 
                    v-for="i in 9" 
                    :key="i" 
                    :label="`摄像头 ${i}`" 
                    :value="`cam${i-1}`"
                  ></el-option>
                </el-select>
              </el-form-item>
            </template>
            
            <template v-else>
              <el-form-item label="摄像头A">
                <el-select 
                  v-model="comparisonSettings.cameraA" 
                  placeholder="选择摄像头A">
                  <el-option 
                    v-for="i in 9" 
                    :key="i" 
                    :label="`摄像头 ${i}`" 
                    :value="`cam${i-1}`"
                  ></el-option>
                </el-select>
              </el-form-item>
              
              <el-form-item label="摄像头B">
                <el-select 
                  v-model="comparisonSettings.cameraB" 
                  placeholder="选择摄像头B">
                  <el-option 
                    v-for="i in 9" 
                    :key="i" 
                    :label="`摄像头 ${i}`" 
                    :value="`cam${i-1}`"
                  ></el-option>
                </el-select>
              </el-form-item>
              
              <el-form-item label="时间范围">
                <el-date-picker
                  v-model="comparisonSettings.timeRange"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  value-format="yyyy-MM-dd"
                ></el-date-picker>
              </el-form-item>
            </template>
            
            <el-form-item>
              <el-button type="primary" @click="generateComparison">生成对比分析</el-button>
            </el-form-item>
          </el-form>
        </div>
        
        <!-- 对比结果 -->
        <div v-if="comparisonResult.generated" class="comparison-results">
          <el-divider content-position="left">对比结果</el-divider>
          
          
          
          <!-- 对比图表 -->
          <el-row :gutter="20" class="comparison-charts">
            <el-col :span="12">
              <el-card class="chart-card">
                <div slot="header">检测数量对比</div>
                <div id="comparisonCountChart" class="chart"></div>
              </el-card>
            </el-col>
            
            <el-col :span="12">
              <el-card class="chart-card">
                <div slot="header">煤块尺寸分布对比</div>
                <div id="comparisonSizeChart" class="chart"></div>
              </el-card>
            </el-col>
          </el-row>
          
          <el-row :gutter="20" class="comparison-charts">
            <el-col :span="12">
              <el-card class="chart-card">
                <div slot="header">置信度分布对比</div>
                <div id="comparisonConfidenceChart" class="chart"></div>
              </el-card>
            </el-col>
            
            <el-col :span="12">
              <el-card class="chart-card">
                <div slot="header">时间分布对比</div>
                <div id="comparisonTimeChart" class="chart"></div>
              </el-card>
            </el-col>
          </el-row>
          
          <!-- 对比分析结论 -->
          <el-card class="insight-card">
            <div slot="header">
              <span>分析洞见</span>
            </div>
            <div class="insights">
              <div 
                v-for="(insight, index) in comparisonResult.insights" 
                :key="index"
                class="insight-item"
              >
                <el-tag :type="insight.type" effect="dark">{{ insight.category }}</el-tag>
                <p>{{ insight.content }}</p>
              </div>
            </div>
          </el-card>
        </div>
      </el-card>
    </div>
    
    
    
    <!-- 日志详情对话框 -->
    <el-dialog
      title="检测日志详情"
      :visible.sync="detailDialogVisible"
      width="75%"
    >
      <div class="log-detail-container" v-if="selectedLog">
        <div class="log-info-panel">
          <h3>基本信息</h3>
          <el-descriptions :column="3" border>
            <el-descriptions-item label="摄像头">
              {{ formatCameraId(selectedLog.camera_id) }}
              </el-descriptions-item>
            <el-descriptions-item label="日期">
              {{ selectedLog.date }}
            </el-descriptions-item>
            <el-descriptions-item label="时间">
              {{ formatTimestamp(selectedLog.timestamp) }}
            </el-descriptions-item>
            <el-descriptions-item label="视频文件">
              {{ getFileName(selectedLog.video_path) }}
            </el-descriptions-item>
            <el-descriptions-item label="文件大小">
              {{ formatFileSize(selectedLog.size || 0) }}
            </el-descriptions-item>
            <el-descriptions-item label="检测数量">
              <el-tag type="primary">{{ selectedLog.detection_count || 0 }}</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </div>
        
        <!-- 检测结果统计 -->
        <div class="detection-stats" v-if="selectedLog.detections && selectedLog.detections.length">
          <h3>检测结果统计</h3>
          <el-row :gutter="20">
            <el-col :span="16">
              <div class="stats-charts">
                <div id="detailSizeChart" class="detail-chart"></div>
                <div id="detailConfidenceChart" class="detail-chart"></div>
              </div>
            </el-col>
            <el-col :span="8">
              <el-card class="stats-card" shadow="hover">
                <div class="stat-item">
                  <div class="stat-label">唯一煤块数</div>
                  <div class="stat-value primary">{{ getUniqueCount(selectedLog) }}</div>
                </div>
                <el-divider></el-divider>
                <div class="stat-item">
                  <div class="stat-label">平均置信度</div>
                  <div class="stat-value warning">{{ getAvgConfidence(selectedLog).toFixed(1) }}%</div>
                </div>
                <el-divider></el-divider>
                <div class="stat-item">
                  <div class="stat-label">尺寸分布</div>
                  <div class="size-distribution compact">
                    <div class="size-label">小型: <span>{{ getSizeCount(selectedLog, 'small') }}</span></div>
                    <div class="size-label">中型: <span>{{ getSizeCount(selectedLog, 'medium') }}</span></div>
                    <div class="size-label">大型: <span>{{ getSizeCount(selectedLog, 'large') }}</span></div>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
        
        <!-- 检测结果详情表格 -->
        <div class="detection-details" v-if="selectedLog.detections && selectedLog.detections.length">
          <h3>检测结果详情</h3>
          <el-table
            :data="selectedLog.detections"
            stripe
            height="350"
            style="width: 100%"
            :default-sort="{prop: 'rel_timestamp', order: 'ascending'}"
          >
            <el-table-column
              label="序号"
              type="index"
              width="60"
              align="center"
            ></el-table-column>
            
            <el-table-column
              prop="track_id"
              label="煤块ID"
              width="80"
              align="center"
              sortable
            ></el-table-column>
            
            <el-table-column
              prop="class"
              label="类别"
              width="80"
              align="center"
            >
              <template slot-scope="scope">
                <el-tag :type="getClassTagType(scope.row.class)" size="small">
                  {{ scope.row.class }}
                </el-tag>
              </template>
            </el-table-column>
            
            <el-table-column
              prop="confidence"
              label="置信度"
              width="120"
              align="center"
              sortable
            >
              <template slot-scope="scope">
                <el-progress
                  :percentage="Math.round(scope.row.confidence * 100)"
                  :status="getConfidenceStatus(scope.row.confidence * 100)"
                ></el-progress>
              </template>
            </el-table-column>
            
            <el-table-column
              label="时间点"
              width="180"
              sortable
              prop="rel_timestamp"
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
              label="尺寸"
              width="80"
              align="center"
            >
              <template slot-scope="scope">
                <el-tag :type="getSizeTagType(scope.row.bbox)" size="small">
                  {{ estimateSize(scope.row.bbox) }}
                </el-tag>
              </template>
            </el-table-column>
            
            <el-table-column
              prop="bbox"
              label="位置坐标"
            >
              <template slot-scope="scope">
                <el-popover
                  placement="right"
                  width="200"
                  trigger="hover"
                >
                  <div class="bbox-detail">
                    <p>左上: ({{ Math.round(scope.row.bbox[0]) }}, {{ Math.round(scope.row.bbox[1]) }})</p>
                    <p>右下: ({{ Math.round(scope.row.bbox[2]) }}, {{ Math.round(scope.row.bbox[3]) }})</p>
                    <p>宽度: {{ Math.round(scope.row.bbox[2] - scope.row.bbox[0]) }}px</p>
                    <p>高度: {{ Math.round(scope.row.bbox[3] - scope.row.bbox[1]) }}px</p>
                    <p>面积: {{ Math.round((scope.row.bbox[2] - scope.row.bbox[0]) * (scope.row.bbox[3] - scope.row.bbox[1])) }}px²</p>
                  </div>
                  <div class="bbox-preview">
                    <div class="bbox-frame">
                      <div 
                        class="bbox-marker" 
                        :style="{
                          left: `${(scope.row.bbox[0] / 1280) * 100}%`, 
                          top: `${(scope.row.bbox[1] / 720) * 100}%`,
                          width: `${((scope.row.bbox[2] - scope.row.bbox[0]) / 1280) * 100}%`, 
                          height: `${((scope.row.bbox[3] - scope.row.bbox[1]) / 720) * 100}%`
                        }"
                      ></div>
                    </div>
                  </div>
                  <el-button slot="reference" type="text">
                    [{{ scope.row.bbox.map(b => Math.round(b)).join(', ') }}]
                  </el-button>
                </el-popover>
              </template>
            </el-table-column>
          </el-table>
        </div>
        
        <!-- 视频预览 -->
        <div class="video-preview" v-if="selectedLog">
          <h3>视频预览</h3>
          <div class="video-container">
            <video 
              ref="detailVideoPlayer" 
              controls 
              class="detail-video"
              v-if="videoUrl"
              :src="videoUrl"
              @error="handleDetailVideoError"
            ></video>
            <div class="video-placeholder" v-else @click="prepareVideo(selectedLog)">
              <i class="el-icon-video-play"></i>
              <p>点击加载视频</p>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
    
    <!-- 视频播放对话框 -->
    <el-dialog
      title="视频回放"
      :visible.sync="videoDialogVisible"
      width="80%"
      :before-close="closeVideoDialog"
    >
      <div class="video-player-container">
        <!-- 主视频播放器 -->
        <video 
          v-if="selectedVideo" 
          ref="videoPlayer" 
          controls 
          class="video-player"
          :src="selectedVideo.url"
          @error="handleVideoError"
        ></video>
        
        <!-- 备用播放器 -->
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
        
        <!-- 检测结果同步显示区 -->
        <div v-if="selectedVideo && detectionResults.length > 0" class="detection-timeline">
          <div class="timeline-header">
            <h3>检测结果时间轴</h3>
            <el-switch
              v-model="showDetectionOverlay"
              active-text="显示检测框"
              inactive-text="隐藏检测框"
            ></el-switch>
          </div>
          
          <div class="timeline-ruler">
            <div class="timeline-track">
              <div 
                v-for="(detection, index) in detectionResults" 
                :key="index"
                class="timeline-marker"
                :style="{ left: `${getTimelinePosition(detection)}%` }"
                :class="{ 'active': isCurrentTimeNear(detection) }"
                @click="seekToTimestamp(detection)"
              ></div>
            </div>
            <div class="timeline-scale">
              <div 
                v-for="i in 10" 
                :key="i" 
                class="timeline-tick"
                :style="{ left: `${i * 10}%` }"
              >
                {{ Math.floor(videoDuration * i / 10) }}s
              </div>
            </div>
          </div>
        </div>
        
        <!-- 检测框覆盖层 -->
        <div 
          v-if="showDetectionOverlay && detectionResults.length > 0" 
          class="detection-overlay"
          :class="{ 'active': selectedVideo }"
        >
          <div 
            v-for="(detection, index) in currentTimeDetections"
            :key="index"
            class="detection-box"
            :style="{
              left: `${detection.bbox[0] / 1280 * 100}%`,
              top: `${detection.bbox[1] / 720 * 100}%`,
              width: `${(detection.bbox[2] - detection.bbox[0]) / 1280 * 100}%`,
              height: `${(detection.bbox[3] - detection.bbox[1]) / 720 * 100}%`,
              borderColor: getClassColor(detection.class)
            }"
          >
            <div class="detection-label" :style="{ backgroundColor: getClassColor(detection.class) }">
              ID:{{ detection.track_id }} {{ Math.round(detection.confidence * 100) }}%
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
    
  
    
    <!-- 导出选项对话框 -->
    <el-dialog
      title="导出数据"
      :visible.sync="exportDialogVisible"
      width="40%"
    >
      <el-form :model="exportForm" label-width="100px">
        <el-form-item label="导出内容">
          <el-radio-group v-model="exportForm.scope">
            <el-radio label="filtered">当前筛选结果</el-radio>
            <el-radio label="all">所有数据</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <el-form-item label="包含字段">
          <el-checkbox-group v-model="exportForm.fields">
            <el-checkbox label="date">日期</el-checkbox>
            <el-checkbox label="time">时间</el-checkbox>
            <el-checkbox label="camera">摄像头</el-checkbox>
            <el-checkbox label="detectionCount">检测数量</el-checkbox>
            <el-checkbox label="confidence">平均置信度</el-checkbox>
            <el-checkbox label="size">尺寸分布</el-checkbox>
            <el-checkbox label="details">检测详情</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        
        <el-form-item label="文件格式">
          <el-radio-group v-model="exportForm.format">
            <el-radio label="csv">CSV</el-radio>
            <el-radio label="excel">Excel</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      
      <div slot="footer" class="dialog-footer">
        <el-button @click="exportDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="exportData" :loading="exporting">导出</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { apiService } from '@/services/api';
import dayjs from 'dayjs';
import weekOfYear from 'dayjs/plugin/weekOfYear';
import io from 'socket.io-client';
import * as echarts from 'echarts'; // 需要安装 echarts
import { saveAs } from 'file-saver';
import * as XLSX from 'xlsx';

// 引入组件
import StatCard from './components/StatCard.vue';
dayjs.extend(weekOfYear);
export default {
  name: 'DetectLogEnhanced',
  components: {
    StatCard
  },
  data() {
    return {
      // 基础数据
      logs: [],
      filteredLogs: [],
      loading: false,
      detailDialogVisible: false,
      videoDialogVisible: false,
      exportDialogVisible: false,
      
      selectedLog: null,
      selectedVideo: null,
      showFallbackPlayer: false,
      videoErrorInfo: null,
      videoUrl: null,
      detectionResults: [],
      baseUrl: 'http://localhost:5000',
      socket: null,
      echartInstances: {},
      
      // 统计数据
      statistics: {
        totalCount: 0,
        uniqueCount: 0,
        avgConfidence: 0,
        videoCount: 0
      },
      
      // 异常数据
      anomalies: [],
      
      // 分页
      currentPage: 1,
      pageSize: 20,
      
      // 视频播放器相关
      videoDuration: 0,
      currentTimeDetections: [],
      showDetectionOverlay: true,
      videoUpdateInterval: null,
      
      // UI控制
      activeTab: 'dashboard',
      trendTimeRange: 'week',
      // showAdvancedFilters: false,
      searchQuery: '',
      sortOption: 'time_desc',
      
      // 导出相关
      exporting: false,
      exportForm: {
        scope: 'filtered',
        fields: ['date', 'time', 'camera', 'detectionCount', 'confidence', 'size'],
        format: 'excel'
      },
      
      
      
      // 过滤器
      filterForm: {
        dateRange: [
          dayjs().subtract(30, 'day').format('YYYY-MM-DD'),
          dayjs().format('YYYY-MM-DD')
        ],
        cameraIds: [],
        // sizes: [],
        confidenceRange: [30, 100],
        // advanced: {
        //   minCount: null,
        //   maxCount: null,
        //   timeSegment: 'allday',
        //   showAnomalies: false
        // }
      },
      pickerOptions: {
        shortcuts: [
          {
            text: '最近一周',
            onClick(picker) {
              const end = new Date();
              const start = new Date();
              start.setTime(start.getTime() - 3600 * 1000 * 24 * 7);
              picker.$emit('pick', [start, end]);
            }
          },
          {
            text: '最近一个月',
            onClick(picker) {
              const end = new Date();
              const start = new Date();
              start.setTime(start.getTime() - 3600 * 1000 * 24 * 30);
              picker.$emit('pick', [start, end]);
            }
          },
          {
            text: '最近三个月',
            onClick(picker) {
              const end = new Date();
              const start = new Date();
              start.setTime(start.getTime() - 3600 * 1000 * 24 * 90);
              picker.$emit('pick', [start, end]);
            }
          }
        ]
      },
      
      // 对比分析
      comparisonSettings: {
        type: 'time',
        timeA: [],
        timeB: [],
        cameraA: null,
        cameraB: null,
        cameraIds: [],
        timeRange: []
      },
      comparisonResult: {
        generated: false,
        labelA: '',
        labelB: '',
        dataA: {
          totalCount: 0,
          uniqueCount: 0,
          avgConfidence: 0,
          videoCount: 0,
          sizeDistribution: { small: 0, medium: 0, large: 0 },
          confidenceDistribution: []
        },
        dataB: {
          totalCount: 0,
          uniqueCount: 0,
          avgConfidence: 0,
          videoCount: 0,
          sizeDistribution: { small: 0, medium: 0, large: 0 },
          confidenceDistribution: []
        },
        insights: []
      }
    };
  },
  computed: {
    paginatedLogs() {
      const start = (this.currentPage - 1) * this.pageSize;
      const end = start + this.pageSize;
      return this.filteredLogs.slice(start, end);
    }
  },
  mounted() {
    this.fetchLogs().then(() => {
      // 初始化摄像头状态
      this.initCameraStatus();
    });
    this.initSocketConnection();
    
  },
  beforeDestroy() {
    // 清理资源
    if (this.socket) {
      this.socket.disconnect();
    }
    this.destroyAllCharts();
    clearInterval(this.videoUpdateInterval);
  },
  methods: {
    // ------------ 基础功能方法 ------------
    initSocketConnection() {
      this.socket = io(this.baseUrl);
      
      this.socket.on('connect', () => {
        console.log('WebSocket connected');
      });
      
      this.socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
      });
    },
    // 初始化摄像头状态
    initCameraStatus() {
      // 创建摄像头状态映射
      this.cameraStatus = {};
      
      // 检查每个摄像头是否有数据
      for (let i = 0; i < 9; i++) {
        const cameraId = `cam${i}`;
        this.cameraStatus[cameraId] = this.hasCameraData(cameraId);
      }
      
      console.log('摄像头状态:', this.cameraStatus);
    },
    async fetchLogs() {
      this.loading = true;
      try {
        // 获取历史记录列表
        const response = await apiService.get(`/api/surveillance/history`);
        this.logs = [];
        
        if (response.data && response.data.length) {
          // 处理每个日期的数据
          for (const dateItem of response.data) {
            const date = dateItem.date;
            
            // 筛选有检测结果的视频
            const videosWithDetections = dateItem.videos.filter(video => video.has_detections);
            
            // 处理每个视频
            for (const video of videosWithDetections) {
              try {
                // 获取实际检测结果
                const detectionResponse = await apiService.get(
                  `/api/surveillance/detection/${date}/${video.filename}`
                );
                
                // 提取检测结果 - 优先使用唯一检测结果
                let detections = [];
                let uniqueCount = 0;
                
                if (detectionResponse.data) {
                  if (detectionResponse.data.unique_detections) {
                    detections = detectionResponse.data.unique_detections;
                    uniqueCount = detectionResponse.data.unique_count || detections.length;
                  } else if (detectionResponse.data.detections) {
                    detections = detectionResponse.data.detections;
                    uniqueCount = detectionResponse.data.unique_count || 0;
                  }
                  
                  // 视频元数据
                  const videoMetadata = detectionResponse.data.video_metadata || {
                    start_time: video.time,
                    duration: 0,
                    fps: 30
                  };
                  
                  // 计算平均置信度
                  let avgConfidence = 0;
                  let totalConfidence = 0;
                  let confidenceCount = 0;
                  
                  detections.forEach(detection => {
                    if (detection.confidence !== undefined) {
                      totalConfidence += detection.confidence;
                      confidenceCount++;
                    }
                  });
                  
                  if (confidenceCount > 0) {
                    avgConfidence = totalConfidence / confidenceCount;
                  }
                  
                  // 计算尺寸分布
                  const sizeDistribution = this.calculateSizeDistribution(detections);
                  
                  // 添加日志条目 - 所有数据都基于真实检测结果
                  this.logs.push({
                    date: date,
                    video_path: video.path,
                    camera_id: this.extractCameraId(video.filename),
                    timestamp: video.time,
                    filename: video.filename,
                    url: video.url,
                    detection_count: detections.length,
                    unique_count: uniqueCount,
                    size: video.size || 0,
                    size_distribution: sizeDistribution,
                    avg_confidence: avgConfidence,
                    detections: detections,
                    videoMetadata: videoMetadata,
                    is_anomaly: this.detectAnomaly(detections, avgConfidence, sizeDistribution)
                  });
                }
              } catch (error) {
                console.error(`获取视频 ${video.filename} 的检测结果失败:`, error);
                
                // 即使获取失败，也添加基本日志条目，但标记为无数据
                this.logs.push({
                  date: date,
                  video_path: video.path,
                  camera_id: this.extractCameraId(video.filename),
                  timestamp: video.time,
                  filename: video.filename,
                  url: video.url,
                  detection_count: 0,
                  unique_count: 0,
                  size: video.size || 0,
                  size_distribution: { small: 0, medium: 0, large: 0 },
                  avg_confidence: 0,
                  detections: [],
                  videoMetadata: { start_time: video.time, duration: 0, fps: 30 },
                  is_anomaly: false,
                  has_data: false // 标记为无数据
                });
              }
            }
          }
        }
        
        // 应用初始筛选
        this.applyFilters();
        
        // 计算统计数据
        this.calculateStatistics();
        
        // 检测异常
        this.detectAnomalies();
        
        // 初始化仪表盘
        this.$nextTick(() => {
          if (this.activeTab === 'dashboard') {
            this.initDashboardCharts();
          }
        });
        
      } catch (error) {
        console.error('获取检测日志失败:', error);
        this.$message.error('获取检测日志失败: ' + (error.response?.data?.error || error.message || '未知错误'));
      } finally {
        this.loading = false;
      }
    },
    refreshData() {
      // 显示加载状态
      this.loading = true;
      // 清空旧数据
      this.logs = [];
      this.filteredLogs = [];
      this.anomalies = [];
      
      // 重新获取所有数据
      this.fetchLogs().then(() => {
        this.$message.success('数据已刷新');
      }).catch(error => {
        this.$message.error('刷新数据失败: ' + error.message);
      });
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
    formatConfidence(value) {
      return `${value}%`;
    },
    getFileName(path) {
      if (!path) return '未知文件';
      return path.split('\\').pop() || path.split('/').pop() || path;
    },
    extractCameraId(filename) {
      const match = filename.match(/cam(\d+)/);
      return match ? `cam${match[1]}` : '未知';
    },
    formatCameraId(cameraId) {
      const match = cameraId.match(/cam(\d+)/);
      return match ? `摄像头 ${parseInt(match[1]) + 1}` : cameraId;
    },
    
    // ------------ 数据处理方法 ------------
    calculateStatistics() {
      // 使用筛选后的日志
      const logs = this.filteredLogs.length > 0 ? this.filteredLogs : this.logs;
      
      // 只使用有数据的日志
      const validLogs = logs.filter(log => log.has_data !== false);
      
      if (validLogs.length === 0) {
        this.statistics = {
          totalCount: 0,
          uniqueCount: 0,
          avgConfidence: 0,
          videoCount: 0
        };
        return;
      }
      
      // 计算总检测数量
      const totalCount = validLogs.reduce((sum, log) => sum + (log.detection_count || 0), 0);
      
      // 计算唯一煤块数 - 使用实际数据
      const uniqueCount = validLogs.reduce((sum, log) => sum + (log.unique_count || 0), 0);
      
      // 计算平均置信度 - 使用加权平均
      let weightedConfidenceSum = 0;
      let totalDetections = 0;
      
      validLogs.forEach(log => {
        if (log.detection_count > 0 && log.avg_confidence !== undefined) {
          weightedConfidenceSum += log.avg_confidence * log.detection_count;
          totalDetections += log.detection_count;
        }
      });
      
      const avgConfidence = totalDetections > 0 ? weightedConfidenceSum / totalDetections : 0;
      
      // 视频数量
      const videoCount = validLogs.length;
      
      // 更新统计数据
      this.statistics = {
        totalCount,
        uniqueCount,
        avgConfidence: avgConfidence * 100, // 转为百分比
        videoCount
      };
      
      console.log('统计数据已更新:', this.statistics);
    },
    calculateSizeDistribution(detections) {
      const distribution = { small: 0, medium: 0, large: 0 };
      
      detections.forEach(detection => {
        if (!detection.bbox) return;
        
        const area = (detection.bbox[2] - detection.bbox[0]) * (detection.bbox[3] - detection.bbox[1]);
        
        if (area < 5000) {
          distribution.small++;
        } else if (area < 20000) {
          distribution.medium++;
        } else {
          distribution.large++;
        }
      });
      
      return distribution;
    },
    detectAnomaly(detections, avgConfidence, sizeDistribution) {
      // 检测结果数量异常
      const tooManyDetections = detections.length > 50;
      
      // 置信度过低异常
      const confTooLow = avgConfidence < 0.5;
      
      // 大型煤块比例过高异常
      const totalSize = sizeDistribution.small + sizeDistribution.medium + sizeDistribution.large;
      const largeRatio = totalSize > 0 ? sizeDistribution.large / totalSize : 0;
      const tooManyLarge = largeRatio > 0.4; // 如果大型煤块超过40%
      
      return tooManyDetections || confTooLow || tooManyLarge;
    },
    detectAnomalies() {
      // 清空现有异常
      this.anomalies = [];
      
      // 使用筛选后的日志
      const logs = this.filteredLogs.length > 0 ? this.filteredLogs : this.logs;
      
      // 只使用有数据的日志
      const validLogs = logs.filter(log => log.has_data !== false);
      
      if (validLogs.length === 0) return;
      
      // 计算检测数量平均值和标准差
      const countValues = validLogs.map(log => log.detection_count || 0);
      const avgCount = countValues.reduce((a, b) => a + b, 0) / countValues.length;
      const stdDevCount = Math.sqrt(
        countValues.reduce((a, b) => a + Math.pow(b - avgCount, 2), 0) / countValues.length
      );
      
      // 计算置信度平均值和标准差
      const confValues = validLogs.map(log => log.avg_confidence || 0);
      const avgConf = confValues.reduce((a, b) => a + b, 0) / confValues.length;
      const stdDevConf = Math.sqrt(
        confValues.reduce((a, b) => a + Math.pow(b - avgConf, 2), 0) / confValues.length
      );
      
      // 检查每个日志是否有异常
      validLogs.forEach(log => {
        // 检测数量异常
        if (log.detection_count > avgCount + 2 * stdDevCount) {
          this.anomalies.push({
            title: `检测数量异常峰值`,
            description: `摄像头${this.formatCameraId(log.camera_id)}在${this.formatTimestamp(log.timestamp)}检测到${log.detection_count}个煤块，明显高于平均值${avgCount.toFixed(0)}`,
            level: 'high',
            timestamp: log.timestamp,
            source: log
          });
        }
        
        // 置信度异常
        if (log.avg_confidence < avgConf - 2 * stdDevConf) {
          this.anomalies.push({
            title: `置信度异常低谷`,
            description: `摄像头${this.formatCameraId(log.camera_id)}在${this.formatTimestamp(log.timestamp)}的检测置信度为${(log.avg_confidence * 100).toFixed(1)}%，明显低于平均值${(avgConf * 100).toFixed(1)}%`,
            level: 'warning',
            timestamp: log.timestamp,
            source: log
          });
        }
        
        // 尺寸分布异常
        const totalSize = log.size_distribution.small + log.size_distribution.medium + log.size_distribution.large;
        if (totalSize > 0) {
          const largeRatio = log.size_distribution.large / totalSize;
          if (largeRatio > 0.4) {
            this.anomalies.push({
              title: `煤块尺寸异常分布`,
              description: `摄像头${this.formatCameraId(log.camera_id)}在${this.formatTimestamp(log.timestamp)}的大型煤块比例为${(largeRatio * 100).toFixed(1)}%，明显高于正常水平`,
              level: largeRatio > 0.6 ? 'high' : 'warning',
              timestamp: log.timestamp,
              source: log
            });
          }
        }
      });
      
      // 按时间排序
      this.anomalies.sort((a, b) => b.timestamp - a.timestamp);
    },
    applyFilters() {
      // 应用筛选条件
      let filtered = [...this.logs];
      
      // 应用日期范围筛选
      if (this.filterForm.dateRange && this.filterForm.dateRange.length === 2) {
        const startDate = this.filterForm.dateRange[0];
        const endDate = this.filterForm.dateRange[1];
        filtered = filtered.filter(log => log.date >= startDate && log.date <= endDate);
      }
      
      // 应用摄像头筛选
      if (this.filterForm.cameraIds && this.filterForm.cameraIds.length > 0) {
          console.log('应用摄像头筛选:', this.filterForm.cameraIds);
          filtered = filtered.filter(log => this.filterForm.cameraIds.includes(log.camera_id));
          
        
        // 调试输出筛选后的结果数量
        console.log('摄像头筛选后数据量:', filtered.length);
        // 如果筛选后没有数据，确保设置为空数组而不是回退到原始数据
        if (filtered.length === 0) {
           console.log('所选摄像头没有数据');
        }
        
      }
    
      
      // 应用置信度范围筛选
      if (this.filterForm.confidenceRange) {
        const minConf = this.filterForm.confidenceRange[0] / 100;
        const maxConf = this.filterForm.confidenceRange[1] / 100;
        filtered = filtered.filter(log => 
          log.avg_confidence >= minConf && 
          log.avg_confidence <= maxConf
        );
      }
      
      // 应用搜索查询
      if (this.searchQuery) {
        const query = this.searchQuery.toLowerCase();
        filtered = filtered.filter(log => 
          this.formatCameraId(log.camera_id).toLowerCase().includes(query) ||
          log.date.toLowerCase().includes(query) ||
          this.getFileName(log.video_path).toLowerCase().includes(query)
        );
      }
      
      // 应用排序
      switch (this.sortOption) {
        case 'time_desc':
          filtered.sort((a, b) => b.timestamp - a.timestamp);
          break;
        case 'time_asc':
          filtered.sort((a, b) => a.timestamp - b.timestamp);
          break;
        case 'count_desc':
          filtered.sort((a, b) => (b.detection_count || 0) - (a.detection_count || 0));
          break;
        case 'confidence_desc':
          filtered.sort((a, b) => (b.avg_confidence || 0) - (a.avg_confidence || 0));
          break;
      }
      
      this.filteredLogs = filtered;
      this.currentPage = 1; // 重置为第一页
      //重新计算统计数据
      this.calculateStatistics();
      // 检测异常
      this.detectAnomalies();
      // 如果在仪表盘页面，更新图表
      if (this.activeTab === 'dashboard') {
        this.$nextTick(() => {
          this.updateDashboardCharts();
        });
      }
     },
     resetFilters() {
      this.filterForm = {
        dateRange: [
          dayjs().subtract(30, 'day').format('YYYY-MM-DD'),
          dayjs().format('YYYY-MM-DD')
        ],
        cameraIds: [],
        // sizes: [],
        confidenceRange: [30, 100],
        // advanced: {
        //   minCount: null,
        //   maxCount: null,
        //   timeSegment: 'allday',
        //   showAnomalies: false
        // }
      };
      this.searchQuery = '';
      this.sortOption = 'time_desc';
      this.applyFilters();
    },
    handleSearch() {
      this.applyFilters();
    },
    handleSortChange() {
      this.applyFilters();
    },
    handleCurrentChange(page) {
      this.currentPage = page;
    },
    handleSizeChange(size) {
      this.pageSize = size;
      this.currentPage = 1;
    },
    onCameraSelectChange(selectedCameras) {
      console.log('摄像头选择变化:', selectedCameras);
      
      // 检查是否选择了未接入的摄像头
      const unavailableCameras = selectedCameras.filter(camId => !this.hasCameraData(camId));
      
      if (unavailableCameras.length > 0) {
        this.$message.warning(`摄像头 ${unavailableCameras.map(id => this.formatCameraId(id)).join(', ')} 没有检测数据`);
      }
      
      // 应用筛选
      this.applyFilters();
    },
    // 检查摄像头是否有数据
    hasCameraData(cameraId) {
      return this.logs.some(log => log.camera_id === cameraId);
    },
    // ------------ 图表方法 ------------
    initDashboardCharts() {
      this.destroyAllCharts();
      this.renderTrendChart();
      this.renderSizeDistributionChart();
      this.renderCameraDistributionChart();
      this.renderConfidenceDistributionChart();
      this.renderTimeHeatmapChart();
    },
    updateDashboardCharts() {
      // 确保所有图表使用筛选后的数据
      this.renderTrendChart();
      this.renderSizeDistributionChart();
      this.renderCameraDistributionChart();
      this.renderConfidenceDistributionChart();
      this.renderTimeHeatmapChart();
    },
    destroyAllCharts() {
      // 销毁所有图表实例以防内存泄漏
      Object.keys(this.echartInstances).forEach(key => {
        if (this.echartInstances[key]) {
          this.echartInstances[key].dispose();
          this.echartInstances[key] = null;
        }
      });
    },
    renderTrendChart() {
      const chartDom = document.getElementById('trendChart');
      if (!chartDom) return;
      
      // 检查是否已存在图表实例，如果存在则直接使用
      let chart = this.echartInstances.trend;
      if (!chart) {
        chart = echarts.init(chartDom);
        this.echartInstances.trend = chart;
      }
      // 根据筛选后的数据聚合趋势数据
      const { dates, counts } = this.aggregateTrendData(this.trendTimeRange);
      
      const option = {
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          }
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: dates,
          axisLabel: {
            rotate: 45,
            interval: 0
          }
        },
        yAxis: {
          type: 'value',
          name: '检测数量'
        },
        series: [
          {
            name: '检测数量',
            type: 'bar',
            data: counts,
            itemStyle: {
              color: '#409EFF'
            }
          }
        ]
      };
      
      chart.setOption(option);
    },
    renderSizeDistributionChart() {
      const chartDom = document.getElementById('sizeDistributionChart');
      if (!chartDom) return;
      
      const chart = echarts.init(chartDom);
      this.echartInstances.sizeDistribution = chart;
      
      // 计算尺寸分布
      const sizeDistribution = {
        small: 0,
        medium: 0,
        large: 0
      };
       // 只在有筛选结果时计算
      if (this.filteredLogs.length > 0) {
        this.filteredLogs.forEach(log => {
          sizeDistribution.small += log.size_distribution.small || 0;
          sizeDistribution.medium += log.size_distribution.medium || 0;
          sizeDistribution.large += log.size_distribution.large || 0;
        });
      }
      // 检查是否所有值都为0
      const totalSize = sizeDistribution.small + sizeDistribution.medium + sizeDistribution.large;
      if (totalSize === 0) {
        // 显示无数据状态
        chart.setOption({
          title: {
            text: '无数据',
            left: 'center',
            top: 'center',
            textStyle: {
              color: '#999',
              fontSize: 16
            }
          }
        });
        return;
      }
      const option = {
        tooltip: {
          trigger: 'item',
          formatter: '{a} <br/>{b}: {c} ({d}%)'
        },
        legend: {
          orient: 'vertical',
          left: 10,
          data: ['小型', '中型', '大型']
        },
        series: [
          {
            name: '尺寸分布',
            type: 'pie',
            radius: ['50%', '70%'],
            avoidLabelOverlap: false,
            label: {
              show: false,
              position: 'center'
            },
            emphasis: {
              label: {
                show: true,
                fontSize: '18',
                fontWeight: 'bold'
              }
            },
            labelLine: {
              show: false
            },
            data: [
              { value: sizeDistribution.small, name: '小型', itemStyle: { color: '#67C23A' } },
              { value: sizeDistribution.medium, name: '中型', itemStyle: { color: '#E6A23C' } },
              { value: sizeDistribution.large, name: '大型', itemStyle: { color: '#F56C6C' } }
            ]
          }
        ]
      };
      
      chart.setOption(option);
    },
    renderCameraDistributionChart() {
      const chartDom = document.getElementById('cameraDistributionChart');
      if (!chartDom) return;
      
      const chart = echarts.init(chartDom);
      this.echartInstances.cameraDistribution = chart;
      
      // 计算摄像头分布
      const cameraDistribution = {};
      
      this.filteredLogs.forEach(log => {
        const cameraId = this.formatCameraId(log.camera_id);
        if (!cameraDistribution[cameraId]) {
          cameraDistribution[cameraId] = 0;
        }
        cameraDistribution[cameraId] += log.detection_count || 0;
      });
      
      const cameraIds = Object.keys(cameraDistribution).sort();
      const countValues = cameraIds.map(id => cameraDistribution[id]);
      
      const option = {
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          }
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: cameraIds
        },
        yAxis: {
          type: 'value',
          name: '检测数量'
        },
        series: [
          {
            name: '检测数量',
            type: 'bar',
            data: countValues,
            itemStyle: {
              color: function(params) {
                const colorList = ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399'];
                return colorList[params.dataIndex % colorList.length];
              }
            }
          }
        ]
      };
      
      chart.setOption(option);
    },
    renderConfidenceDistributionChart() {
      const chartDom = document.getElementById('confidenceDistributionChart');
      if (!chartDom) return;
      
      const chart = echarts.init(chartDom);
      this.echartInstances.confidenceDistribution = chart;
      
      // 修复: 计算置信度分布 - 基于实际检测结果而非日志条目
      const confidenceDistribution = [0, 0, 0, 0, 0]; // 0-20%, 20-40%, 40-60%, 60-80%, 80-100%
      
      this.filteredLogs.forEach(log => {
        // 确保有检测结果
        if (log.detections && log.detections.length > 0) {
          // 遍历每个煤块的检测结果
          log.detections.forEach(detection => {
            // 确保置信度值存在
            if (detection.confidence !== undefined) {
              const confidence = detection.confidence; // 直接使用检测结果的置信度
              const index = Math.min(Math.floor(confidence * 5), 4);
              confidenceDistribution[index]++;
            }
          });
        }
      });
      
      // 检查是否有数据
      const totalDetections = confidenceDistribution.reduce((sum, val) => sum + val, 0);
      if (totalDetections === 0) {
        // 显示无数据状态
        chart.setOption({
          title: {
            text: '无数据',
            left: 'center',
            top: 'center',
            textStyle: {
              color: '#999',
              fontSize: 16
            }
          }
        });
        return;
      }

      const option = {
        tooltip: {
          trigger: 'item',
          formatter: '{a} <br/>{b}: {c}个 ({d}%)'
        },
        legend: {
          orient: 'vertical',
          right: 10,
          data: ['0-20%', '20-40%', '40-60%', '60-80%', '80-100%']
        },
        series: [
          {
            name: '置信度分布',
            type: 'pie',
            radius: ['30%', '60%'],
            center: ['40%', '50%'],
            avoidLabelOverlap: false,
            label: {
              show: true,
              formatter: '{b}: {c}个'  // 显示个数
            },
            emphasis: {
              label: {
                show: true,
                fontSize: '16',
                fontWeight: 'bold'
              }
            },
            data: [
              { value: confidenceDistribution[0], name: '0-20%', itemStyle: { color: '#F56C6C' } },
              { value: confidenceDistribution[1], name: '20-40%', itemStyle: { color: '#E6A23C' } },
              { value: confidenceDistribution[2], name: '40-60%', itemStyle: { color: '#909399' } },
              { value: confidenceDistribution[3], name: '60-80%', itemStyle: { color: '#67C23A' } },
              { value: confidenceDistribution[4], name: '80-100%', itemStyle: { color: '#409EFF' } }
            ]
          }
        ]
      };
      
      chart.setOption(option);
    },
    renderTimeHeatmapChart() {
      const chartDom = document.getElementById('timeHeatmapChart');
      if (!chartDom) return;
      
      const chart = echarts.init(chartDom);
      this.echartInstances.timeHeatmap = chart;
      
      // 生成热力图数据
      const hours = Array.from(Array(24).keys());
      const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
      
      const data = [];
      const dayMap = { 0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5 }; // 将JS的0=周日映射到6
      
      // 初始化空数据
      for (let i = 0; i < 7; i++) {
        for (let j = 0; j < 24; j++) {
          data.push([j, i, 0]);
        }
      }
      
      // 填充实际数据
      this.filteredLogs.forEach(log => {
        const date = new Date(log.timestamp * 1000);
        const hour = date.getHours();
        const dayOfWeek = dayMap[date.getDay()]; // 转换为热图索引
        
        // 获取对应的数据点
        const dataPoint = data.find(item => item[0] === hour && item[1] === dayOfWeek);
        if (dataPoint) {
          dataPoint[2] += log.detection_count || 0;
        }
      });
      
      const option = {
        tooltip: {
          position: 'top',
          formatter: function (params) {
            return `${days[params.data[1]]} ${params.data[0]}:00<br>检测数量: ${params.data[2]}`;
          }
        },
        grid: {
          height: '70%',
          top: '10%'
        },
        xAxis: {
          type: 'category',
          data: hours.map(h => `${h}:00`),
          axisTick: {
            alignWithLabel: true
          },
          axisLabel: {
            interval: 3
          }
        },
        yAxis: {
          type: 'category',
          data: days,
          splitArea: {
            show: true
          }
        },
        visualMap: {
          min: 0,
          max: Math.max(...data.map(item => item[2])),
          calculable: true,
          orient: 'horizontal',
          left: 'center',
          bottom: '0%',
          inRange: {
            color: ['#ebedf0', '#c6e48b', '#7bc96f', '#239a3b', '#196127']
          }
        },
        series: [{
          name: '检测时间分布',
          type: 'heatmap',
          data: data,
          label: {
            show: false
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }]
      };
      
      chart.setOption(option);
    },
    renderDetailCharts() {
      if (!this.selectedLog || !this.selectedLog.detections) return;
      
      this.$nextTick(() => {
        // 渲染检测尺寸分布图
        this.renderDetailSizeChart();
        
        // 渲染检测置信度分布图
        this.renderDetailConfidenceChart();
      });
    },
    renderDetailSizeChart() {
      const chartDom = document.getElementById('detailSizeChart');
      if (!chartDom) return;
      
      const chart = echarts.init(chartDom);
      this.echartInstances.detailSize = chart;
      
      // 获取尺寸分布
      const sizeDistribution = {
        small: this.getSizeCount(this.selectedLog, 'small'),
        medium: this.getSizeCount(this.selectedLog, 'medium'),
        large: this.getSizeCount(this.selectedLog, 'large')
      };
      
      const option = {
        title: {
          text: '煤块尺寸分布',
          left: 'center'
        },
        tooltip: {
          trigger: 'item',
          formatter: '{b}: {c} ({d}%)'
        },
        series: [
          {
            type: 'pie',
            radius: '70%',
            center: ['50%', '50%'],
            data: [
              { value: sizeDistribution.small, name: '小型', itemStyle: { color: '#67C23A' } },
              { value: sizeDistribution.medium, name: '中型', itemStyle: { color: '#E6A23C' } },
              { value: sizeDistribution.large, name: '大型', itemStyle: { color: '#F56C6C' } }
            ],
            label: {
              formatter: '{b}: {c} ({d}%)'
            },
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowOffsetX: 0,
                shadowColor: 'rgba(0, 0, 0, 0.5)'
              }
            }
          }
        ]
      };
      
      chart.setOption(option);
    },
    renderDetailConfidenceChart() {
      const chartDom = document.getElementById('detailConfidenceChart');
      if (!chartDom) return;
      
      const chart = echarts.init(chartDom);
      this.echartInstances.detailConfidence = chart;
      
      // 计算置信度分布
      const confidenceRanges = [
        { min: 0, max: 0.3, label: '低 (0-30%)' },
        { min: 0.3, max: 0.6, label: '中 (30-60%)' },
        { min: 0.6, max: 0.8, label: '高 (60-80%)' },
        { min: 0.8, max: 1, label: '极高 (80-100%)' }
      ];
      
      const confidenceCounts = Array(confidenceRanges.length).fill(0);
      
      if (this.selectedLog.detections) {
        this.selectedLog.detections.forEach(detection => {
          const confidence = detection.confidence || 0;
          for (let i = 0; i < confidenceRanges.length; i++) {
            if (confidence >= confidenceRanges[i].min && confidence < confidenceRanges[i].max) {
              confidenceCounts[i]++;
              break;
            }
          }
        });
      }
      
      const option = {
        title: {
          text: '置信度分布',
          left: 'center'
        },
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          }
        },
        xAxis: {
          type: 'category',
          data: confidenceRanges.map(range => range.label)
        },
        yAxis: {
          type: 'value',
          name: '数量'
        },
        series: [
          {
            name: '置信度',
            type: 'bar',
            data: confidenceCounts,
            itemStyle: {
              color: function(params) {
                const colors = ['#F56C6C', '#E6A23C', '#67C23A', '#409EFF'];
                return colors[params.dataIndex];
              }
            }
          }
        ]
      };
      
      chart.setOption(option);
    },
    updateTrendChart() {
      // 重新渲染趋势图
      this.renderTrendChart();
    },
    aggregateTrendData(timeRange) {
      // 使用筛选后的日志
      const logs = this.filteredLogs.length > 0 ? this.filteredLogs : this.logs;
      
      // 只使用有效日志
      const validLogs = logs.filter(log => log.has_data !== false);
      
      const dateFormat = timeRange === 'day' ? 'MM-DD' :'MM月';
      const dateMap = {};
      
      validLogs.forEach(log => {
        const date = dayjs(log.timestamp * 1000);
        let key;
        
        if (timeRange === 'day') {
          // 按天
          key = date.format(dateFormat);
        } else if (timeRange === 'week') {
          // 按周 - 使用直接获取周数的方式
          const year = date.year();
          const weekNum = date.week(); // 获取当前周数
          
          // 确保周数是两位数格式，比如"01"而不是"1"
          const formattedWeek = weekNum < 10 ? `0${weekNum}` : `${weekNum}`;
          
          // 生成唯一的周标识符: "年份-第XX周"
          key = `${year}-第${formattedWeek}周`; 
        } else {
          // 按月
          key = `${date.year()}-${date.format(dateFormat)}`;
        }
        
        if (!dateMap[key]) {
          dateMap[key] = 0;
        }
        
        dateMap[key] += log.detection_count || 0;
      });
      
      // 转换为数组并排序
      const sortedEntries = Object.entries(dateMap);
        if (timeRange === 'day') {
          // 按天排序 (MM-DD格式)
          sortedEntries.sort((a, b) => a[0].localeCompare(b[0]));
        } else if (timeRange === 'week') {
          // 按周排序 (YYYY-第XX周格式)
          sortedEntries.sort((a, b) => {
            // 提取年份和周数部分
            const [yearA, weekA] = a[0].split('-第');
            const [yearB, weekB] = b[0].split('-第');
            
            // 先按年份排序
            if (yearA !== yearB) {
              return yearA.localeCompare(yearB);
            }
            
            // 再按周数排序（去掉"周"字）
            const weekNumA = parseInt(weekA.replace('周', ''));
            const weekNumB = parseInt(weekB.replace('周', ''));
            return weekNumA - weekNumB;
          });
        } else {
          // 按月排序 (YYYY-MM月格式)
          sortedEntries.sort((a, b) => a[0].localeCompare(b[0]));
        }
      
      return {
        dates: sortedEntries.map(entry => entry[0]),
        counts: sortedEntries.map(entry => entry[1])
      };
    },
    
    // ------------ 图表辅助方法 ------------
    generateRandomSizeDistribution() {
      // 生成随机大小分布 (小型, 中型, 大型)
      const total = Math.floor(Math.random() * 50) + 10; // 10-60
      const small = Math.floor(total * (Math.random() * 0.5 + 0.2)); // 20%-70% 小型
      const medium = Math.floor(total * (Math.random() * 0.4 + 0.1)); // 10%-50% 中型
      const large = total - small - medium; // 剩余为大型
      
      return {
        small,
        medium,
        large
      };
    },
    getSizeCount(log, size) {
      if (!log || !log.size_distribution) return 0;
      return log.size_distribution[size] || 0;
    },
    getSizePercentage(log, size) {
      if (!log || !log.size_distribution) return 0;
      
      const total = log.size_distribution.small + log.size_distribution.medium + log.size_distribution.large;
      if (total === 0) return 0;
      
      return (log.size_distribution[size] / total) * 100;
    },
    getAvgConfidence(log) {
      if (!log) return 0;
      return log.avg_confidence ? log.avg_confidence * 100 : 50; // 默认50%
    },
    getConfidenceStatus(confidence) {
      if (confidence >= 80) return 'success';
      if (confidence >= 60) return 'warning';
      return 'exception';
    },
    getConfidenceType(confidence) {
      const percent = confidence * 100;
      if (percent >= 80) return 'success';
      if (percent >= 60) return 'warning';
      return 'danger';
    },
    getUniqueCount(log) {
      // 估算唯一煤块数 (实际应从后端获取)
      return Math.floor((log.detection_count || 0) * 0.7);
    },
    getSizeTagType(bbox) {
      if (!bbox || bbox.length < 4) return 'info';
      
      const area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]);
      
      if (area < 5000) return 'info';
      if (area < 20000) return 'warning';
      return 'danger';
    },
    getClassTagType(className) {
      const types = {
        'coal': 'danger',
        'rock': 'warning',
        'default': 'primary'
      };
      return types[className] || types.default;
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
    estimateSize(bbox) {
      if (!bbox || bbox.length < 4) return '未知';
      
      const area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]);
      
      if (area < 5000) return '小型';
      if (area < 20000) return '中型';
      return '大型';
    },
    getRowClass({ row }) {
      if (row.is_anomaly) return 'anomaly-row';
      return '';
    },
    
    // ------------ 对话框方法 ------------
    async showLogDetail(log) {
      try {
        this.selectedLog = { ...log };
        
        // 重置视频播放状态
        this.videoUrl = null;
        
        // 加载详细检测结果
        if (log.date && log.filename) {
          const response = await apiService.get(`/api/surveillance/detection/${log.date}/${log.filename}`);
          if (response.data && (response.data.detections || response.data.unique_detections)) {
            // 优先使用唯一煤块检测结果
            this.selectedLog.detections = response.data.unique_detections || response.data.detections;
            
            // 保存视频元数据
            this.selectedLog.videoMetadata = response.data.video_metadata || {
              start_time: log.timestamp,
              duration: 0,
              fps: 30
            };
          }
        }
        
        this.detailDialogVisible = true;
        
        // 渲染详情图表
        this.$nextTick(() => {
          this.renderDetailCharts();
        });
      } catch (error) {
        console.error('获取检测详情失败:', error);
        this.$message.error('获取检测详情失败: ' + error.message);
      }
    },
    async prepareVideo(log) {
      if (!log) return;
      
      try {
        this.$message.info('正在准备视频播放...');
        
        // 构建视频URL
        const videoUrl = `${this.baseUrl}/surveillance/${log.date}/${log.filename}?t=${Date.now()}`;
        
        // 获取认证token
        const token = localStorage.getItem('token');
        
        // 尝试使用fetch加载视频数据
        const response = await fetch(videoUrl, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        if (!response.ok) {
          throw new Error(`HTTP错误! 状态码: ${response.status}`);
        }
        
        const blob = await response.blob();
        console.log(`接收到视频数据，大小: ${(blob.size/1024/1024).toFixed(2)}MB`);
        
        // 创建Blob URL
        const blobUrl = URL.createObjectURL(blob);
        this.videoUrl = blobUrl;
        
        this.$message.success('视频加载成功!');
        
        // 设置视频播放器
        this.$nextTick(() => {
          const videoElement = this.$refs.detailVideoPlayer;
          if (videoElement) {
            videoElement.addEventListener('loadedmetadata', () => {
              console.log(`视频元数据加载完成，时长: ${videoElement.duration}秒`);	
              });
            }
          });
        }   
    catch (error) {
        console.error('无法加载视频:', error);
        this.$message.error(`无法加载视频: ${error.message}`);
      }
    },
    handleDetailVideoError(event) {
      console.error('视频播放失败:', event);
      this.$message.error('视频播放失败，请尝试在完整播放器中查看');
    },
    playVideo(log) {
      this.selectedLog = { ...log };
      this.detectionResults = this.selectedLog.detections || [];
      
      // 设置视频URL
      this.selectedVideo = {
        url: `${this.baseUrl}/surveillance/${log.date}/${log.filename}?t=${Date.now()}`
      };
      
      // 重置视频播放状态
      this.showFallbackPlayer = false;
      this.videoErrorInfo = null;
      this.currentTimeDetections = [];
      
      this.videoDialogVisible = true;
      
      // 加载检测结果
      this.loadDetectionResults(log);
      
      // 设置视频播放检查计时器
      this.$nextTick(() => {
        if (this.videoUpdateInterval) {
          clearInterval(this.videoUpdateInterval);
        }
        
        this.videoUpdateInterval = setInterval(() => {
          this.updateCurrentTimeDetections();
        }, 200); // 5fps更新频率
      });
    },
    async loadDetectionResults(log) {
      try {
        if (log.date && log.filename) {
          const response = await apiService.get(`/api/surveillance/detection/${log.date}/${log.filename}`);
          if (response.data) {
            // 优先使用唯一煤块检测结果
            this.detectionResults = response.data.unique_detections || response.data.detections || [];
            
            // 处理检测结果中的时间戳
            this.detectionResults = this.detectionResults.map(detection => {
              // 确保有相对时间戳
              if (detection.rel_timestamp === undefined && detection.abs_timestamp !== undefined && log.timestamp) {
                detection.rel_timestamp = detection.abs_timestamp - log.timestamp;
              }
              return detection;
            });
            
            // 设置视频元数据
            this.videoDuration = response.data.video_metadata?.duration || 0;
          }
        }
      } catch (error) {
        console.error('获取检测结果失败:', error);
        this.$message.warning('无法加载检测结果: ' + error.message);
      }
    },
    updateCurrentTimeDetections() {
      const videoElement = this.$refs.videoPlayer;
      if (!videoElement || !this.detectionResults.length) return;
      
      const currentTime = videoElement.currentTime;
      
      // 查找当前时间点附近的检测结果
      this.currentTimeDetections = this.detectionResults.filter(detection => {
        const detectionTime = detection.rel_timestamp || 0;
        return Math.abs(detectionTime - currentTime) < 0.5; // 0.5秒内的检测
      });
    },
    isCurrentTimeNear(detection) {
      const videoElement = this.$refs.videoPlayer;
      if (!videoElement) return false;
      
      const currentTime = videoElement.currentTime;
      const detectionTime = detection.rel_timestamp || 0;
      
      return Math.abs(detectionTime - currentTime) < 0.5; // 0.5秒内
    },
    getTimelinePosition(detection) {
      if (!detection.rel_timestamp || this.videoDuration <= 0) return 0;
      
      // 计算在时间轴上的位置百分比
      return (detection.rel_timestamp / this.videoDuration) * 100;
    },
    seekToTimestamp(detection) {
      const videoElement = this.$refs.videoPlayer || this.$refs.detailVideoPlayer;
      if (!videoElement) return;
      
      if (detection.rel_timestamp !== undefined) {
        videoElement.currentTime = detection.rel_timestamp;
        videoElement.play().catch(e => console.error('播放失败:', e));
      }
    },
    formatDetectionTimestamp(detection) {
      // 优先使用相对时间戳
      if (detection.rel_timestamp !== undefined) {
        const minutes = Math.floor(detection.rel_timestamp / 60);
        const seconds = Math.floor(detection.rel_timestamp % 60);
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
      }
      
      return "时间未知";
    },
    closeVideoDialog() {
      // 暂停视频播放
      if (this.$refs.videoPlayer) {
        this.$refs.videoPlayer.pause();
      }
      
      // 清理计时器
      if (this.videoUpdateInterval) {
        clearInterval(this.videoUpdateInterval);
        this.videoUpdateInterval = null;
      }
      
      this.videoDialogVisible = false;
      this.selectedVideo = null;
      this.currentTimeDetections = [];
    },
    handleVideoError(event) {
      console.error('视频播放失败:', event);
      this.$message.error('视频播放失败，正在尝试备用播放器');
      this.showFallbackPlayer = true;
    },
    handleFallbackError(event) {
      console.error('备用播放器也失败了:', event);
      this.$message.error('备用播放器也失败了，请检查视频格式和服务器配置');
    },
    
    // ------------ 报表和导出方法 ------------
    showExportOptions() {
      // 显示导出选项对话框
      this.exportDialogVisible = true;
    },
    exportData() {
      // 执行数据导出
      this.exporting = true;
      
      try {
        // 准备导出数据
        const dataToExport = this.exportForm.scope === 'filtered' ? this.filteredLogs : this.logs;
        
        // 格式化导出数据
        const exportedData = dataToExport.map(log => {
          const data = {};
          
          // 根据选择的字段添加数据
          if (this.exportForm.fields.includes('date')) {
            data['日期'] = log.date;
          }
          
          if (this.exportForm.fields.includes('time')) {
            data['时间'] = this.formatTimestamp(log.timestamp);
          }
          
          if (this.exportForm.fields.includes('camera')) {
            data['摄像头'] = this.formatCameraId(log.camera_id);
          }
          
          if (this.exportForm.fields.includes('detectionCount')) {
            data['检测数量'] = log.detection_count || 0;
          }
          
          if (this.exportForm.fields.includes('confidence')) {
            data['平均置信度'] = log.avg_confidence ? (log.avg_confidence * 100).toFixed(1) + '%' : '0%';
          }
          
          if (this.exportForm.fields.includes('size')) {
            data['小型煤块'] = log.size_distribution?.small || 0;
            data['中型煤块'] = log.size_distribution?.medium || 0;
            data['大型煤块'] = log.size_distribution?.large || 0;
          }
          
          if (this.exportForm.fields.includes('details')) {
            data['视频文件'] = this.getFileName(log.video_path);
            data['文件大小'] = this.formatFileSize(log.size || 0);
          }
          
          return data;
        });
        
        // 导出到所选格式
        if (this.exportForm.format === 'csv') {
          this.exportToCSV(exportedData);
        } else {
          this.exportToExcel(exportedData);
        }
        
        this.$message.success('数据导出成功!');
      } catch (error) {
        console.error('导出失败:', error);
        this.$message.error('导出失败: ' + error.message);
      } finally {
        this.exporting = false;
        this.exportDialogVisible = false;
      }
    },
    exportToCSV(data) {
      if (!data || !data.length) return;
      
      // 获取表头
      const headers = Object.keys(data[0]);
      
      // 创建CSV内容
      let csvContent = headers.join(',') + '\n';
      
      // 添加数据行
      data.forEach(item => {
        const row = headers.map(header => {
          // 确保字段内容中的逗号和换行符不会破坏CSV格式
          const cell = String(item[header] || '');
          if (cell.includes(',') || cell.includes('\n') || cell.includes('"')) {
            return `"${cell.replace(/"/g, '""')}"`;
          }
          return cell;
        });
        csvContent += row.join(',') + '\n';
      });
      
      // 创建Blob并下载
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      saveAs(blob, `检测日志_${timestamp}.csv`);
    },
    exportToExcel(data) {
      if (!data || !data.length) return;
      
      // 创建工作簿
      const wb = XLSX.utils.book_new();
      
      // 将数据转换为工作表
      const ws = XLSX.utils.json_to_sheet(data);
      
      // 将工作表添加到工作簿
      XLSX.utils.book_append_sheet(wb, ws, "检测日志");
      
      // 生成Excel文件
      const excelBuffer = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
      
      // 保存文件
      const blob = new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      saveAs(blob, `检测日志_${timestamp}.xlsx`);
    },

    // ------------ 对比分析方法 ------------
    generateComparison() {
      // 验证输入
      let valid = true;
      let errorMsg = '';
      
      if (this.comparisonSettings.type === 'time') {
        if (!this.comparisonSettings.timeA || this.comparisonSettings.timeA.length !== 2) {
          valid = false;
          errorMsg = '请选择时间段A';
        } else if (!this.comparisonSettings.timeB || this.comparisonSettings.timeB.length !== 2) {
          valid = false;
          errorMsg = '请选择时间段B';
        }
      } else {
        if (!this.comparisonSettings.cameraA) {
          valid = false;
          errorMsg = '请选择摄像头A';
        } else if (!this.comparisonSettings.cameraB) {
          valid = false;
          errorMsg = '请选择摄像头B';
        } else if (!this.comparisonSettings.timeRange || this.comparisonSettings.timeRange.length !== 2) {
          valid = false;
          errorMsg = '请选择时间范围';
        }
      }
      
      if (!valid) {
        this.$message.warning(errorMsg);
        return;
      }
      
      // 执行对比分析
      try {
        // 准备对比数据
        let filtersA, filtersB, labelA, labelB;
        
        if (this.comparisonSettings.type === 'time') {
          // 时间段对比
          labelA = `${this.comparisonSettings.timeA[0]} 至 ${this.comparisonSettings.timeA[1]}`;
          labelB = `${this.comparisonSettings.timeB[0]} 至 ${this.comparisonSettings.timeB[1]}`;
          
          filtersA = {
            dateRange: this.comparisonSettings.timeA,
            cameraIds: this.comparisonSettings.cameraIds
          };
      
          filtersB = {
            dateRange: this.comparisonSettings.timeB,
            cameraIds: this.comparisonSettings.cameraIds
          };
        } else {
          // 摄像头对比
          labelA = this.formatCameraId(this.comparisonSettings.cameraA);
          labelB = this.formatCameraId(this.comparisonSettings.cameraB);
          
          filtersA = {
            dateRange: this.comparisonSettings.timeRange,
            cameraIds: [this.comparisonSettings.cameraA]
          };
          
          filtersB = {
            dateRange: this.comparisonSettings.timeRange,
            cameraIds: [this.comparisonSettings.cameraB]
          };
        }
        // 获取筛选后的数据集
        const dataA = this.getFilteredDataset(filtersA);
        const dataB = this.getFilteredDataset(filtersB);
        // 计算A组统计数据
        const statsA = this.calculateComparisonStats(dataA);
        
        // 计算B组统计数据
        const statsB = this.calculateComparisonStats(dataB);
        
        // 生成分析洞见
        const insights = this.generateInsights(statsA, statsB, labelA, labelB);
        
        // 更新对比结果
        this.comparisonResult = {
          generated: true,
          labelA,
          labelB,
          dataA: statsA,
          dataB: statsB,
          insights
        };
        
        // 渲染对比图表
        this.$nextTick(() => {
          this.renderComparisonCharts();
        });
      } catch (error) {
        console.error('生成对比分析失败:', error);
        this.$message.error('生成对比分析失败: ' + error.message);
      }
    },
    calculateComparisonStats(data) {
      // 处理空数据情况
      if (!data || data.length === 0) {
        return {
          totalCount: 0,
          uniqueCount: 0,
          avgConfidence: 0,
          videoCount: 0,
          sizeDistribution: { small: 0, medium: 0, large: 0 },
          confidenceDistribution: [0, 0, 0, 0, 0],
          hourlyDistribution: Array(24).fill(0)
        };
      }
      
      const totalCount = data.reduce((sum, log) => sum + (log.detection_count || 0), 0);
      const uniqueCount = data.reduce((sum, log) => sum + (log.unique_count || 0), 0);
      const avgConfidence = data.reduce((sum, log) => sum + (log.avg_confidence || 0), 0) / data.length || 0;
      const videoCount = data.length;
      
      // 计算尺寸分布
      const sizeDistribution = {
        small: 0,
        medium: 0,
        large: 0
      };
      
      data.forEach(log => {
        sizeDistribution.small += log.size_distribution?.small || 0;
        sizeDistribution.medium += log.size_distribution?.medium || 0;
        sizeDistribution.large += log.size_distribution?.large || 0;
      });
      
      // 计算置信度分布
      const confidenceDistribution = [0, 0, 0, 0, 0]; // 0-20%, 20-40%, 40-60%, 60-80%, 80-100%

      data.forEach(log => {
        // 确保有检测结果
        if (log.detections && log.detections.length > 0) {
          // 遍历每个煤块的检测结果
          log.detections.forEach(detection => {
            // 确保置信度值存在
            if (detection.confidence !== undefined) {
              const confidence = detection.confidence;
              const index = Math.min(Math.floor(confidence * 5), 4);
              confidenceDistribution[index]++;
            }
          });
        }
      });
      // 计算时间分布
      const hourlyDistribution = Array(24).fill(0);

      data.forEach(log => {
        if (log.timestamp) {
          const hour = new Date(log.timestamp * 1000).getHours();
          hourlyDistribution[hour] += log.detection_count || 0;
        }
      });
      
      return {
        totalCount,
        uniqueCount,
        avgConfidence,
        videoCount,
        sizeDistribution,
        confidenceDistribution,
        hourlyDistribution
      };
    },
    generateInsights(statsA, statsB, labelA, labelB) {
      // 生成分析洞见
      const insights = [];
      
      // 检测数量对比
      const countDiff = statsA.totalCount - statsB.totalCount;
      const countDiffPercent = statsB.totalCount === 0 ? 100 : (countDiff / statsB.totalCount) * 100;
      
      if (Math.abs(countDiffPercent) > 10) {
        insights.push({
          category: '检测数量',
          content: countDiff > 0 ? 
            `${labelA}的检测数量比${labelB}高出${Math.abs(countDiffPercent).toFixed(1)}%，可能表明该时段产量更高或检测更频繁。` :
            `${labelA}的检测数量比${labelB}低${Math.abs(countDiffPercent).toFixed(1)}%，可能表明该时段产量下降或设备灵敏度下降。`,
          type: countDiff > 0 ? 'success' : 'warning'
        });
      }
      
      // 置信度对比
      const confDiff = statsA.avgConfidence - statsB.avgConfidence;
      if (Math.abs(confDiff) > 0.05) {
        insights.push({
          category: '置信度',
          content: confDiff > 0 ? 
            `${labelA}的平均置信度比${labelB}高出${(confDiff * 100).toFixed(1)}%，表明检测质量有所提升。` :
            `${labelA}的平均置信度比${labelB}低${Math.abs(confDiff * 100).toFixed(1)}%，可能需要调整检测设置或检查设备状态。`,
          type: confDiff > 0 ? 'success' : 'warning'
        });
      }
      
      // 尺寸分布对比
      const totalSizeA = statsA.sizeDistribution.small + statsA.sizeDistribution.medium + statsA.sizeDistribution.large;
      const totalSizeB = statsB.sizeDistribution.small + statsB.sizeDistribution.medium + statsB.sizeDistribution.large;
      
      if (totalSizeA > 0 && totalSizeB > 0) {
        const largePercentA = statsA.sizeDistribution.large / totalSizeA;
        const largePercentB = statsB.sizeDistribution.large / totalSizeB;
        const largeDiff = largePercentA - largePercentB;
        
        if (Math.abs(largeDiff) > 0.1) {
          insights.push({
            category: '尺寸分布',
            content: largeDiff > 0 ? 
              `${labelA}的大型煤块比例比${labelB}高出${(largeDiff * 100).toFixed(1)}%，表明破碎效果可能需要改进。` :
              `${labelA}的大型煤块比例比${labelB}低${Math.abs(largeDiff * 100).toFixed(1)}%，表明破碎效果有所改善。`,
            type: largeDiff > 0 ? 'warning' : 'success'
          });
        }
      }
      
      // 如果洞见太少，添加一个一般性观察
      if (insights.length === 0) {
        insights.push({
          category: '总体观察',
          content: `${labelA}与${labelB}的检测数据相似，没有发现显著差异。`,
          type: 'info'
        });
      }
      
      return insights;
    },
    getFilteredDataset(filters) {
      // 筛选数据集
      let filtered = [...this.logs];
      
      // 应用日期范围筛选
      if (filters.dateRange && filters.dateRange.length === 2) {
        filtered = filtered.filter(log => 
          log.date >= filters.dateRange[0] && log.date <= filters.dateRange[1]
        );
      }
      
      // 应用摄像头筛选
      if (filters.cameraIds && filters.cameraIds.length > 0) {
        filtered = filtered.filter(log => filters.cameraIds.includes(log.camera_id));
      }
      
      // 应用置信度范围筛选（如果需要）
      if (filters.confidenceRange) {
        const minConf = filters.confidenceRange[0] / 100;
        const maxConf = filters.confidenceRange[1] / 100;
        filtered = filtered.filter(log => 
          log.avg_confidence >= minConf && log.avg_confidence <= maxConf
        );
      }
      
      return filtered;
    },
    renderComparisonCharts() {
      // 渲染对比分析图表
      this.renderComparisonCountChart();
      this.renderComparisonSizeChart();
      this.renderComparisonConfidenceChart();
      this.renderComparisonTimeChart();
    },
    renderComparisonCountChart() {
      const chartDom = document.getElementById('comparisonCountChart');
      if (!chartDom) return;
      
      const chart = echarts.init(chartDom);
      this.echartInstances.comparisonCount = chart;
      
      const option = {
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          }
        },
        legend: {
          data: ['检测总数', '唯一煤块']
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: [this.comparisonResult.labelA, this.comparisonResult.labelB]
        },
        yAxis: {
          type: 'value',
          name: '数量'
        },
        series: [
          {
            name: '检测总数',
            type: 'bar',
            data: [
              this.comparisonResult.dataA.totalCount,
              this.comparisonResult.dataB.totalCount
            ],
            itemStyle: {
              color: '#409EFF'
            }
          },
          {
            name: '唯一煤块',
            type: 'bar',
            data: [
              this.comparisonResult.dataA.uniqueCount,
              this.comparisonResult.dataB.uniqueCount
            ],
            itemStyle: {
              color: '#67C23A'
            }
          }
        ]
      };
      
      chart.setOption(option);
    },
    renderComparisonSizeChart() {
      const chartDom = document.getElementById('comparisonSizeChart');
      if (!chartDom) return;
      
      const chart = echarts.init(chartDom);
      this.echartInstances.comparisonSize = chart;
      
      const option = {
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          }
        },
        legend: {
          data: ['小型', '中型', '大型']
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: [this.comparisonResult.labelA, this.comparisonResult.labelB]
        },
        yAxis: {
          type: 'value',
          name: '数量'
        },
        series: [
          {
            name: '小型',
            type: 'bar',
            stack: '尺寸',
            emphasis: {
              focus: 'series'
            },
            data: [
              this.comparisonResult.dataA.sizeDistribution.small,
              this.comparisonResult.dataB.sizeDistribution.small
            ],
            itemStyle: {
              color: '#67C23A'
            }
          },
          {
            name: '中型',
            type: 'bar',
            stack: '尺寸',
            emphasis: {
              focus: 'series'
            },
            data: [
              this.comparisonResult.dataA.sizeDistribution.medium,
              this.comparisonResult.dataB.sizeDistribution.medium
            ],
            itemStyle: {
              color: '#E6A23C'
            }
          },
          {
            name: '大型',
            type: 'bar',
            stack: '尺寸',
            emphasis: {
              focus: 'series'
            },
            data: [
              this.comparisonResult.dataA.sizeDistribution.large,
              this.comparisonResult.dataB.sizeDistribution.large
            ],
            itemStyle: {
              color: '#F56C6C'
            }
          }
        ]
      };
      
      chart.setOption(option);
    },
    renderComparisonConfidenceChart() {
      const chartDom = document.getElementById('comparisonConfidenceChart');
      if (!chartDom) return;
      
      const chart = echarts.init(chartDom);
      this.echartInstances.comparisonConfidence = chart;
      
      const option = {
        tooltip: {
          trigger: 'item',
          formatter: '{a} <br/>{b} : {c}%'
        },
        legend: {
          left: 'center',
          data: [this.comparisonResult.labelA, this.comparisonResult.labelB]
        },
        radar: {
          indicator: [
            { name: '0-20%', max: 100 },
            { name: '20-40%', max: 100 },
            { name: '40-60%', max: 100 },
            { name: '60-80%', max: 100 },
            { name: '80-100%', max: 100 }
          ]
        },
        series: [
          {
            name: '置信度分布',
            type: 'radar',
            data: [
              {
                value: this.normalizeConfidenceData(this.comparisonResult.dataA.confidenceDistribution),
                name: this.comparisonResult.labelA,
                itemStyle: {
                  color: '#409EFF'
                },
                areaStyle: {
                  color: 'rgba(64, 158, 255, 0.6)'
                }
              },
              {
                value: this.normalizeConfidenceData(this.comparisonResult.dataB.confidenceDistribution),
                name: this.comparisonResult.labelB,
                itemStyle: {
                  color: '#67C23A'
                },
                areaStyle: {
                  color: 'rgba(103, 194, 58, 0.6)'
                }
              }
            ]
          }
        ]
      };
      chart.setOption(option);
    },
    renderComparisonTimeChart() {
      const chartDom = document.getElementById('comparisonTimeChart');
      if (!chartDom) return;
      
      const chart = echarts.init(chartDom);
      this.echartInstances.comparisonTime = chart;
      
      // 初始化小时分布数组
      const hoursA = Array(24).fill(0);
      const hoursB = Array(24).fill(0);
      // 使用已筛选的数据集填充A组
      this.comparisonResult.dataA.hourlyDistribution.forEach((count, hour) => {
        hoursA[hour] = count;
      });
      
      // 使用已筛选的数据集填充B组
      this.comparisonResult.dataB.hourlyDistribution.forEach((count, hour) => {
        hoursB[hour] = count;
      });
      
      const hours = Array.from(Array(24).keys()).map(h => `${h}:00`);
      
      const option = {
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          }
        },
        legend: {
          data: [this.comparisonResult.labelA, this.comparisonResult.labelB]
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: [
          {
            type: 'category',
            data: hours,
            axisLabel: {
              interval: 3
            }
          }
        ],
        yAxis: [
          {
            type: 'value',
            name: '检测数量'
          }
        ],
        series: [
          {
            name: this.comparisonResult.labelA,
            type: 'line',
            smooth: true,
            data: hoursA,
            itemStyle: {
              color: '#409EFF'
            },
            areaStyle: {
              color: 'rgba(64, 158, 255, 0.2)'
            }
          },
          {
            name: this.comparisonResult.labelB,
            type: 'line',
            smooth: true,
            data: hoursB,
            itemStyle: {
              color: '#67C23A'
            },
            areaStyle: {
              color: 'rgba(103, 194, 58, 0.2)'
            }
          }
        ]
      };
      
      chart.setOption(option);
    },
    normalizeConfidenceData(data) {
      // 将置信度数据归一化为百分比
      const total = data.reduce((sum, val) => sum + val, 0);
      if (total === 0) return [0, 0, 0, 0, 0];
      
      return data.map(val => (val / total) * 100);
    },
    
    // ------------ UI控制方法 ------------
    handleTabChange(tab) {
      // 处理标签页切换
      if (tab.name === 'dashboard' && this.activeTab !== 'dashboard') {
        // 当切换到仪表盘时，初始化图表
        this.$nextTick(() => {
          this.initDashboardCharts();
        });
      } else if (tab.name === 'comparison' && this.activeTab !== 'comparison') {
        // 重置对比结果
        this.comparisonResult.generated = false;
      }
    },
  }
};
</script>

<style scoped>
.detect-log-container {
  padding: 20px;
}

.filter-card, .chart-card, .anomaly-card, .insight-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.advanced-filter {
  background-color: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  margin-bottom: 20px;
}

.range-separator {
  margin: 0 10px;
}

.stats-summary {
  margin: 20px 0;
}

.dashboard-row {
  margin-bottom: 20px;
}

.chart {
  height: 300px;
}

.pie-chart {
  height: 350px;
}

.heatmap-chart {
  height: 400px;
}

.anomaly-item {
  padding: 10px;
  border-radius: 4px;
  background-color: #f5f7fa;
}

.anomaly-item h4 {
  margin: 0 0 5px 0;
  color: #f56c6c;
}

.anomaly-item p {
  margin: 0 0 10px 0;
  color: #606266;
}

.size-distribution {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.size-bar {
  height: 16px;
  background-color: #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  width: 100%;
}

.size-segment {
  height: 100%;
  text-align: center;
  font-size: 12px;
  color: white;
  line-height: 16px;
  min-width: 30px;
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

.expanded-row {
  padding: 15px;
}

.video-thumbnail {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.thumbnail-placeholder {
  width: 100%;
  height: 150px;
  background-color: #f5f7fa;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  border: 1px dashed #dcdfe6;
}

.thumbnail-placeholder i {
  font-size: 40px;
  color: #909399;
  margin-bottom: 10px;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}

.anomaly-row {
  background-color: rgba(245, 108, 108, 0.1);
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

.fallback-player {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #ebeef5;
}

.detection-timeline {
  position: relative;
  padding: 10px 0;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.timeline-header h3 {
  margin: 0;
}

.timeline-ruler {
  position: relative;
  height: 40px;
}

.timeline-track {
  position: relative;
  height: 10px;
  background-color: #f5f7fa;
  border-radius: 5px;
}

.timeline-marker {
  position: absolute;
  width: 4px;
  height: 10px;
  background-color: #409EFF;
  cursor: pointer;
  transition: all 0.2s;
}

.timeline-marker:hover {
  background-color: #F56C6C;
  height: 16px;
  top: -3px;
}

.timeline-marker.active {
  background-color: #F56C6C;
  height: 16px;
  top: -3px;
}

.timeline-scale {
  position: relative;
  height: 20px;
}

.timeline-tick {
  position: absolute;
  font-size: 12px;
  color: #909399;
  transform: translateX(-50%);
}

.detection-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 100;
  display: none;
}

.detection-overlay.active {
  display: block;
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

.log-detail-container {
  padding: 10px;
}

.log-info-panel {
  margin-bottom: 20px;
}

.detection-stats {
  margin: 20px 0;
}

.stats-charts {
  display: flex;
  gap: 20px;
}

.detail-chart {
  width: 50%;
  height: 250px;
}

.stats-card {
  height: 100%;
}

.stat-item {
  margin-bottom: 15px;
}

.stat-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 5px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
}

.stat-value.primary {
  color: #409EFF;
}

.stat-value.success {
  color: #67C23A;
}

.stat-value.warning {
  color: #E6A23C;
}

.stat-value.danger {
  color: #F56C6C;
}

.size-distribution.compact {
  font-size: 14px;
}

.size-label {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
}

.video-preview {
  margin-top: 20px;
}

.video-container {
  width: 100%;
  border-radius: 4px;
  overflow: hidden;
  background-color: #000;
}

.detail-video {
  width: 100%;
  max-height: 400px;
}

.video-placeholder {
  width: 100%;
  height: 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  background-color: #1c1c1c;
  color: #fff;
}

.video-placeholder i {
  font-size: 60px;
  margin-bottom: 10px;
}

.comparison-settings {
  margin-bottom: 20px;
}

.comparison-card {
  height: 100%;
}

.comparison-charts {
  margin-bottom: 20px;
}

.insights {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.insight-item {
  padding: 15px;
  border-radius: 4px;
  background-color: #f5f7fa;
  border-left: 5px solid #409EFF;
}

.insight-item .el-tag {
  margin-bottom: 10px;
}

.bbox-preview {
  margin-top: 10px;
  width: 100%;
  height: 120px;
}

.bbox-frame {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: #f5f7fa;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
}

.bbox-marker {
  position: absolute;
  border: 2px solid #F56C6C;
  box-sizing: border-box;
}
</style>