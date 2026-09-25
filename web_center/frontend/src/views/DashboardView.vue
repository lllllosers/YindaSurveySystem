<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  Connection,
  DataBoard,
  Files,
  OfficeBuilding,
  Document,
} from "@element-plus/icons-vue";
import {
  getDatabaseHealth,
  getHealth,
  getOverview,
  type OverviewResponse,
} from "../api/system";
import aqueductHero from "../assets/zhuanglang-aqueduct-hero.png";

type ServiceState = "checking" | "online" | "offline";

const apiState = ref<ServiceState>("checking");
const dbState = ref<ServiceState>("checking");
const overview = ref<OverviewResponse | null>(null);
const checking = ref(false);
const heroStyle = {
  backgroundImage: `linear-gradient(90deg, rgba(5, 21, 49, .94) 0%, rgba(8, 39, 78, .80) 48%, rgba(7, 34, 67, .26) 100%), url(${aqueductHero})`,
};

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
      })
      .catch(() => {
        apiState.value = "offline";
      }),
    getDatabaseHealth()
      .then((data) => {
        dbState.value = data.status === "ok" ? "online" : "offline";
      })
      .catch(() => {
        dbState.value = "offline";
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
      <div class="eyebrow">调查工作总览</div>
      <h1>工作台</h1>
      <p>从任务安排到成果入库，在这里掌握本轮调查工作的整体进展。</p>
    </div>
    <el-button :icon="Connection" :loading="checking" @click="checkServices">
      重新检测服务
    </el-button>
  </div>

  <section class="hero-panel hero-aqueduct" :style="heroStyle">
    <div>
      <div class="hero-badge"><span></span> 中心管理平台运行正常</div>
      <h2>让现场调查有任务、有依据<br />让每份成果可核验、可追溯</h2>
      <p>庄浪河大渡槽 · 中心统一安排，基层桌面端离线调查，成果回传集中管理。</p>
    </div>
    <div class="hero-version">
      <span>当前调查标准</span>
      <strong>{{ overview?.product_version ?? "V1.2.0" }}</strong>
      <small>桌面端与中心端数据标准一致</small>
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
      <div><span>正式成果</span><strong>{{ overview?.central_record_count ?? "—" }}</strong><small>{{ overview?.pending_review_count ?? 0 }} 个成果待审核</small></div>
    </div>
    <div class="metric-card">
      <div class="metric-icon amber"><Document /></div>
      <div><span>调查任务</span><strong>{{ overview?.survey_task_count ?? "—" }}</strong><small>中心已安排的调查工作</small></div>
    </div>
  </div>

  <el-card shadow="never" class="business-card collaboration-card">
    <template #header>
      <div class="card-header">
        <span>中心端与桌面端如何配合</span>
        <small>一套数据标准贯穿全过程</small>
      </div>
    </template>
    <div class="collaboration-flow">
      <div><b>1</b><strong>建立项目批次</strong><span>中心明确本次调查范围和时间</span></div>
      <i>→</i>
      <div><b>2</b><strong>下发调查任务</strong><span>下载任务文件交给管理处或水管所</span></div>
      <i>→</i>
      <div><b>3</b><strong>桌面端现场调查</strong><span>无网络也能录入表格和照片</span></div>
      <i>→</i>
      <div><b>4</b><strong>回传调查成果</strong><span>桌面端导出成果文件并上传中心</span></div>
      <i>→</i>
      <div><b>5</b><strong>审核并形成成果库</strong><span>自动核对范围，减少人工汇总</span></div>
    </div>
  </el-card>

  <div class="dashboard-lower">
    <el-card shadow="never" class="business-card service-panel">
      <template #header>
        <div class="card-header"><span>系统运行情况</span><small>出现异常时可重新检测</small></div>
      </template>
      <div class="service-row">
        <div class="service-status-dot" :class="apiState"></div>
        <div class="service-detail"><strong>业务服务</strong><span>负责登录、任务和成果处理</span></div>
        <el-tag :type="apiStatusType" effect="light">{{ apiState === "online" ? "运行正常" : apiState === "checking" ? "检测中" : "连接失败" }}</el-tag>
      </div>
      <div class="service-row">
        <div class="service-status-dot" :class="dbState"></div>
        <div class="service-detail"><strong>数据服务</strong><span>负责安全保存中心业务数据</span></div>
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
      <div class="version-line">组织、渠道和分管范围已统一校验</div>
    </el-card>
  </div>
</template>
