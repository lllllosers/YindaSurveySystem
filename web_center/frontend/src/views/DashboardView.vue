<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  Connection,
  DataBoard,
  Files,
  OfficeBuilding,
  User,
} from "@element-plus/icons-vue";
import {
  getDatabaseHealth,
  getHealth,
  getOverview,
  type OverviewResponse,
} from "../api/system";

type ServiceState = "checking" | "online" | "offline";

const apiState = ref<ServiceState>("checking");
const dbState = ref<ServiceState>("checking");
const apiService = ref("-");
const dbName = ref("-");
const dbUser = ref("-");
const overview = ref<OverviewResponse | null>(null);
const checking = ref(false);

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
  checking.value = true;
  apiState.value = "checking";
  dbState.value = "checking";

  await Promise.all([
    getHealth()
      .then((data) => {
        apiState.value = data.status === "ok" ? "online" : "offline";
        apiService.value = data.service;
      })
      .catch(() => {
        apiState.value = "offline";
        apiService.value = "-";
      }),
    getDatabaseHealth()
      .then((data) => {
        dbState.value = data.status === "ok" ? "online" : "offline";
        dbName.value = data.database;
        dbUser.value = data.user;
      })
      .catch(() => {
        dbState.value = "offline";
        dbName.value = "-";
        dbUser.value = "-";
      }),
    getOverview()
      .then((data) => (overview.value = data))
      .catch(() => (overview.value = null)),
  ]);
  checking.value = false;
}

onMounted(checkServices);
</script>

<template>
  <div class="intro dashboard-intro">
    <div class="intro-copy">
      <div class="eyebrow">OPERATIONS OVERVIEW</div>
      <h1>工作台</h1>
      <p>集中查看项目、调查批次、成果回传与正式主数据状态。</p>
    </div>
    <el-button :icon="Connection" :loading="checking" @click="checkServices">
      重新检测服务
    </el-button>
  </div>

  <section class="hero-panel">
    <div>
      <div class="hero-badge"><span></span> Web Center Preview 已就绪</div>
      <h2>引大入秦灌区现状调查<br />中央管理入口</h2>
      <p>桌面端负责离线调查，Web 中心负责主数据、任务协同与成果归集。</p>
    </div>
    <div class="hero-version">
      <span>当前业务版本</span>
      <strong>{{ overview?.product_version ?? "V1.2.0" }}</strong>
      <small>{{ overview?.task_protocol ?? ".ydtask V3" }} · {{ overview?.result_protocol ?? ".ydresult 2.2" }}</small>
    </div>
  </section>

  <div class="dashboard-grid">
    <div class="metric-card">
      <div class="metric-icon indigo"><DataBoard /></div>
      <div><span>项目总数</span><strong>{{ overview?.project_count ?? "—" }}</strong><small>中央项目档案</small></div>
    </div>
    <div class="metric-card">
      <div class="metric-icon cyan"><Connection /></div>
      <div><span>进行中批次</span><strong>{{ overview?.active_batch_count ?? "—" }}</strong><small>当前有效调查批次</small></div>
    </div>
    <div class="metric-card">
      <div class="metric-icon green"><Files /></div>
      <div><span>成果提交</span><strong>{{ overview?.result_submission_count ?? "—" }}</strong><small>已接收成果包</small></div>
    </div>
    <div class="metric-card">
      <div class="metric-icon amber"><User /></div>
      <div><span>启用用户</span><strong>{{ overview?.active_user_count ?? "—" }}</strong><small>可登录系统账户</small></div>
    </div>
  </div>

  <div class="dashboard-lower">
    <el-card shadow="never" class="business-card service-panel">
      <template #header>
        <div class="card-header"><span>服务运行状态</span><small>本机开发环境</small></div>
      </template>
      <div class="service-row">
        <div class="service-status-dot" :class="apiState"></div>
        <div class="service-detail"><strong>Web API</strong><span>{{ apiService }}</span></div>
        <el-tag :type="apiStatusType" effect="light">{{ apiState === "online" ? "运行正常" : apiState === "checking" ? "检测中" : "连接失败" }}</el-tag>
      </div>
      <div class="service-row">
        <div class="service-status-dot" :class="dbState"></div>
        <div class="service-detail"><strong>PostgreSQL</strong><span>{{ dbName }} · {{ dbUser }}</span></div>
        <el-tag :type="dbStatusType" effect="light">{{ dbState === "online" ? "运行正常" : dbState === "checking" ? "检测中" : "连接失败" }}</el-tag>
      </div>
    </el-card>

    <el-card shadow="never" class="business-card master-panel">
      <template #header>
        <div class="card-header"><span>正式主数据</span><router-link to="/master-data">查看详情</router-link></div>
      </template>
      <div class="master-overview">
        <div class="master-orb"><el-icon><OfficeBuilding /></el-icon></div>
        <div class="master-numbers">
          <div><strong>{{ overview?.official_department_count ?? "—" }}</strong><span>管理处</span></div>
          <div><strong>{{ overview?.official_office_count ?? "—" }}</strong><span>管理所</span></div>
          <div><strong>{{ overview?.official_canal_count ?? "—" }}</strong><span>渠道</span></div>
          <div><strong>{{ overview?.official_scope_count ?? "—" }}</strong><span>范围</span></div>
        </div>
      </div>
      <div class="version-line">正式基线 {{ overview?.master_data_version ?? "—" }}</div>
    </el-card>
  </div>
</template>
