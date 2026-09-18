<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  Connection,
  DataAnalysis,
  Document,
  Files,
  Management,
  Operation,
  Setting,
} from "@element-plus/icons-vue";
import { getDatabaseHealth, getHealth } from "./api/system";

type ServiceState = "checking" | "online" | "offline";

const apiState = ref<ServiceState>("checking");
const dbState = ref<ServiceState>("checking");
const apiService = ref("-");
const dbName = ref("-");
const dbUser = ref("-");

const apiStatusType = computed(() => {
  if (apiState.value === "online") return "success";
  if (apiState.value === "offline") return "danger";
  return "warning";
});

const dbStatusType = computed(() => {
  if (dbState.value === "online") return "success";
  if (dbState.value === "offline") return "danger";
  return "warning";
});

const apiStatusText = computed(() => {
  if (apiState.value === "online") return "API 已连接";
  if (apiState.value === "offline") return "API 未连接";
  return "正在检测";
});

const dbStatusText = computed(() => {
  if (dbState.value === "online") return "PostgreSQL 已连接";
  if (dbState.value === "offline") return "PostgreSQL 未连接";
  return "正在检测";
});

async function checkServices() {
  apiState.value = "checking";
  dbState.value = "checking";

  try {
    const data = await getHealth();
    apiState.value = data.status === "ok" ? "online" : "offline";
    apiService.value = data.service;
  } catch (error) {
    apiState.value = "offline";
    apiService.value = "-";
    console.error(error);
  }

  try {
    const data = await getDatabaseHealth();
    dbState.value = data.status === "ok" ? "online" : "offline";
    dbName.value = data.database;
    dbUser.value = data.user;
  } catch (error) {
    dbState.value = "offline";
    dbName.value = "-";
    dbUser.value = "-";
    console.error(error);
  }
}

onMounted(checkServices);
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
        default-active="dashboard"
        class="side-menu"
        background-color="transparent"
        text-color="#c8d1dc"
        active-text-color="#ffffff"
      >
        <el-menu-item index="dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item index="projects" disabled>
          <el-icon><Management /></el-icon>
          <span>项目与批次</span>
        </el-menu-item>
        <el-menu-item index="canals" disabled>
          <el-icon><Operation /></el-icon>
          <span>组织与渠系</span>
        </el-menu-item>
        <el-menu-item index="tasks" disabled>
          <el-icon><Document /></el-icon>
          <span>任务中心</span>
        </el-menu-item>
        <el-menu-item index="results" disabled>
          <el-icon><Files /></el-icon>
          <span>成果中心</span>
        </el-menu-item>
        <el-menu-item index="system" disabled>
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div>
          <div class="page-title">Web 中心实验环境</div>
          <div class="page-subtitle">
            experiment/web-hybrid · Stage 01.3
          </div>
        </div>
        <div class="top-status">
          <el-tag :type="apiStatusType" effect="light" size="large">
            {{ apiStatusText }}
          </el-tag>
          <el-tag :type="dbStatusType" effect="light" size="large">
            {{ dbStatusText }}
          </el-tag>
        </div>
      </el-header>

      <el-main class="content">
        <div class="intro">
          <div>
            <h1>引大入秦灌区现状调查数据中心</h1>
            <p>
              当前阶段验证浏览器 → Vue → FastAPI → PostgreSQL 完整开发链路。
            </p>
          </div>
          <el-button :icon="Connection" type="primary" @click="checkServices">
            重新检测服务
          </el-button>
        </div>

        <el-row :gutter="18">
          <el-col :xs="24" :md="12" :lg="6">
            <el-card shadow="never" class="status-card">
              <template #header><span>前端</span></template>
              <div class="metric-value">Vue 3</div>
              <div class="metric-note">TypeScript · Vite · Element Plus</div>
            </el-card>
          </el-col>

          <el-col :xs="24" :md="12" :lg="6">
            <el-card shadow="never" class="status-card">
              <template #header><span>后端 API</span></template>
              <div class="metric-value">
                <el-text :type="apiStatusType" size="large">
                  {{ apiStatusText }}
                </el-text>
              </div>
              <div class="metric-note">{{ apiService }}</div>
            </el-card>
          </el-col>

          <el-col :xs="24" :md="12" :lg="6">
            <el-card shadow="never" class="status-card">
              <template #header><span>数据库</span></template>
              <div class="metric-value">
                <el-text :type="dbStatusType" size="large">
                  {{ dbStatusText }}
                </el-text>
              </div>
              <div class="metric-note">{{ dbName }}</div>
            </el-card>
          </el-col>

          <el-col :xs="24" :md="12" :lg="6">
            <el-card shadow="never" class="status-card">
              <template #header><span>数据库身份</span></template>
              <div class="metric-value service-name">{{ dbUser }}</div>
              <div class="metric-note">应用独立角色 · 非 postgres 超级用户</div>
            </el-card>
          </el-col>
        </el-row>

        <el-card shadow="never" class="roadmap-card">
          <template #header>
            <div class="card-header">
              <span>后续业务模块</span>
              <el-tag type="info">基础设施阶段</el-tag>
            </div>
          </template>

          <el-steps :active="0" align-center>
            <el-step title="项目与批次" description="中心主数据" />
            <el-step title="组织与渠系" description="组织树、渠系、渠段" />
            <el-step title="任务中心" description=".ydtask 发放" />
            <el-step title="成果中心" description=".ydresult 接收与预检" />
            <el-step title="审核汇总" description="冲突、编号、统计" />
          </el-steps>
        </el-card>
      </el-main>
    </el-container>
  </el-container>
</template>
