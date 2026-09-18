<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Connection } from "@element-plus/icons-vue";
import { getDatabaseHealth, getHealth } from "../api/system";

type ServiceState = "checking" | "online" | "offline";

const apiState = ref<ServiceState>("checking");
const dbState = ref<ServiceState>("checking");
const apiService = ref("-");
const dbName = ref("-");
const dbUser = ref("-");

const apiStatusType = computed(() =>
  apiState.value === "online"
    ? "success"
    : apiState.value === "offline"
      ? "danger"
      : "warning",
);

const dbStatusType = computed(() =>
  dbState.value === "online"
    ? "success"
    : dbState.value === "offline"
      ? "danger"
      : "warning",
);

async function checkServices() {
  apiState.value = "checking";
  dbState.value = "checking";

  try {
    const data = await getHealth();
    apiState.value = data.status === "ok" ? "online" : "offline";
    apiService.value = data.service;
  } catch {
    apiState.value = "offline";
    apiService.value = "-";
  }

  try {
    const data = await getDatabaseHealth();
    dbState.value = data.status === "ok" ? "online" : "offline";
    dbName.value = data.database;
    dbUser.value = data.user;
  } catch {
    dbState.value = "offline";
    dbName.value = "-";
    dbUser.value = "-";
  }
}

onMounted(checkServices);
</script>

<template>
  <div class="intro">
    <div>
      <h1>工作台</h1>
      <p>浏览器 → Vue → FastAPI → PostgreSQL 中央开发链路。</p>
    </div>
    <el-button :icon="Connection" type="primary" @click="checkServices">
      重新检测服务
    </el-button>
  </div>

  <el-row :gutter="18">
    <el-col :span="8">
      <el-card shadow="never" class="status-card">
        <template #header>后端 API</template>
        <div class="metric-value">
          <el-text :type="apiStatusType" size="large">
            {{ apiState === "online" ? "API 已连接" : "API 未连接" }}
          </el-text>
        </div>
        <div class="metric-note">{{ apiService }}</div>
      </el-card>
    </el-col>

    <el-col :span="8">
      <el-card shadow="never" class="status-card">
        <template #header>PostgreSQL</template>
        <div class="metric-value">
          <el-text :type="dbStatusType" size="large">
            {{
              dbState === "online"
                ? "PostgreSQL 已连接"
                : "PostgreSQL 未连接"
            }}
          </el-text>
        </div>
        <div class="metric-note">{{ dbName }}</div>
      </el-card>
    </el-col>

    <el-col :span="8">
      <el-card shadow="never" class="status-card">
        <template #header>数据库身份</template>
        <div class="metric-value service-name">{{ dbUser }}</div>
        <div class="metric-note">应用独立角色 · 非超级用户</div>
      </el-card>
    </el-col>
  </el-row>

  <el-card shadow="never" class="roadmap-card">
    <template #header>
      <div class="card-header">
        <span>Web 中心业务链</span>
        <el-tag type="success">Stage 02 已开始</el-tag>
      </div>
    </template>

    <el-steps :active="1" align-center>
      <el-step title="项目与批次" description="本阶段" />
      <el-step title="组织与渠系" description="下一阶段" />
      <el-step title="任务中心" description=".ydtask" />
      <el-step title="成果中心" description=".ydresult" />
      <el-step title="审核汇总" description="冲突、编号、统计" />
    </el-steps>
  </el-card>
</template>
