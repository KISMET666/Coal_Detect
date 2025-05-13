import Vue from 'vue'
import Vuex from 'vuex'

Vue.use(Vuex)

export default new Vuex.Store({
  state: {
    // 实时监测状态
    monitoringStatus: {
      isDetecting: false,
      startTime: null,
      recordingTime: 0,
      currentSegment: 1,
      totalSegments: 1,
      activeCameras: []
    }
  },
  mutations: {
    // 开始检测
    START_DETECTION(state, cameraIds) {
      state.monitoringStatus.isDetecting = true;
      state.monitoringStatus.startTime = Date.now();
      state.monitoringStatus.recordingTime = 0;
      state.monitoringStatus.currentSegment = 1;
      state.monitoringStatus.activeCameras = cameraIds || [];
    },
    // 停止检测
    STOP_DETECTION(state) {
      state.monitoringStatus.isDetecting = false;
      state.monitoringStatus.startTime = null;
      state.monitoringStatus.activeCameras = [];
    },
    // 更新录制时间
    UPDATE_RECORDING_TIME(state, time) {
      state.monitoringStatus.recordingTime = time;
    },
    // 更新片段信息
    UPDATE_SEGMENT_INFO(state, { currentSegment, totalSegments }) {
      state.monitoringStatus.currentSegment = currentSegment;
      state.monitoringStatus.totalSegments = totalSegments;
    }
  },
  actions: {
    // 开始检测
    startDetection({ commit }, cameraIds) {
      commit('START_DETECTION', cameraIds);
    },
    // 停止检测
    stopDetection({ commit }) {
      commit('STOP_DETECTION');
    },
    // 更新录制时间
    updateRecordingTime({ commit }, time) {
      commit('UPDATE_RECORDING_TIME', time);
    },
    // 更新片段信息
    updateSegmentInfo({ commit }, segmentInfo) {
      commit('UPDATE_SEGMENT_INFO', segmentInfo);
    }
  },
  getters: {
    // 是否正在检测
    isDetecting: state => state.monitoringStatus.isDetecting,
    // 获取录制时间
    recordingTime: state => state.monitoringStatus.recordingTime,
    // 获取片段信息
    segmentInfo: state => ({
      currentSegment: state.monitoringStatus.currentSegment,
      totalSegments: state.monitoringStatus.totalSegments
    }),
    // 获取活跃摄像头
    activeCameras: state => state.monitoringStatus.activeCameras
  }
})