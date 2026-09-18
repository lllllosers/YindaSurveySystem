<script setup lang="ts">
import { useRoute } from "vue-router";
import {
  DataAnalysis,
  Document,
  Files,
  Management,
  Operation,
  Setting,
} from "@element-plus/icons-vue";

const route = useRoute();
</script>

<template>
  <el-container class="app-shell">
    <el-aside width="232px" class="sidebar">
      <div class="brand">
        <div class="brand-mark">引</div>
        <div>
          <div class="brand-title">引大调查中心</div>
          <div class="brand-subtitle">Yinda Survey Center</div>
        </div>
      </div>

      <el-menu
        :default-active="route.path"
        router
        class="side-menu"
        background-color="transparent"
        text-color="#c8d1dc"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/">
          <el-icon><DataAnalysis /></el-icon>
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item index="/projects">
          <el-icon><Management /></el-icon>
          <span>项目与批次</span>
        </el-menu-item>
        <el-menu-item index="/canals" disabled>
          <el-icon><Operation /></el-icon>
          <span>组织与渠系</span>
        </el-menu-item>
        <el-menu-item index="/tasks" disabled>
          <el-icon><Document /></el-icon>
          <span>任务中心</span>
        </el-menu-item>
        <el-menu-item index="/results" disabled>
          <el-icon><Files /></el-icon>
          <span>成果中心</span>
        </el-menu-item>
        <el-menu-item index="/settings" disabled>
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div>
          <div class="page-title">引大入秦灌区现状调查数据中心</div>
          <div class="page-subtitle">experiment/web-hybrid</div>
        </div>
        <el-tag type="info" effect="plain">Stage 02.1</el-tag>
      </el-header>

      <el-main class="content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
