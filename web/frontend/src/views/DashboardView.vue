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
import { useAuthStore } from "../stores/auth";

type ServiceState = "checking" | "online" | "offline";
interface WorkPrompt { title: string; description: string; path: string; action: string; tone: "blue" | "amber" | "green"; }

const apiState = ref<ServiceState>("checking");
const dbState = ref<ServiceState>("checking");
const overview = ref<OverviewResponse | null>(null);
const checking = ref(false);
const auth = useAuthStore();
const roleTitle = computed(() => ({
  admin: "系统管理与业务总览",
  manager: "调查组织与业务办理",
  reviewer: "成果核验与审核",
  viewer: "调查成果查询",
}[auth.user?.role ?? "viewer"]));
const roleDescription = computed(() => ({
  admin: "管理用户权限、调查业务和中心正式成果。",
  manager: "安排调查任务、维护业务资料并跟进成果入库。",
  reviewer: "优先处理待核验成果，并查询已经入库的调查记录。",
  viewer: "查看项目、调查任务和正式成果，跟踪整体进展。",
}[auth.user?.role ?? "viewer"]));
const heroStyle = {
  backgroundImage: `linear-gradient(90deg, rgba(5, 21, 49, .94) 0%, rgba(8, 39, 78, .80) 48%, rgba(7, 34, 67, .26) 100%), url(${aqueductHero})`,
};
const workPrompts = computed<WorkPrompt[]>(() => {
  const data = overview.value;
  if (!data) return [];
  const items: WorkPrompt[] = [];
  const canPrepare =
    auth.hasPermission("projects.write")
    || auth.hasPermission("master_data.write")
    || auth.hasPermission("tasks.write");
  const canReview = auth.hasPermission("results.review") || auth.hasPermission("online_entries.review");
  if (auth.isAdmin && data.pending_user_count > 0) {
    items.push({ title: `审核 ${data.pending_user_count} 项账户申请`, description: "核对申请人身份，在用户与权限页面启用账户并分配工作角色。", path: "/users", action: "审核账户", tone: "amber" });
  }
  if (canPrepare && data.active_batch_count === 0) {
    items.push({ title: "建立进行中的调查批次", description: "任务必须归入一个进行中的批次，项目、任务和成果才能对应起来。", path: "/projects", action: "前往项目批次", tone: "blue" });
  }
  if (auth.hasPermission("master_data.write") && data.unassigned_backbone_canal_count > 0) {
    items.push({ title: `补齐 ${data.unassigned_backbone_canal_count} 条骨干渠分管`, description: "给干渠和分干渠按管理所、桩号区段设置负责范围，之后才能准确下发任务。", path: "/master-data", action: "前往单位与渠系", tone: "amber" });
  }
  if (
    auth.hasPermission("tasks.write")
    && data.active_batch_count > 0
    && data.survey_task_count === 0
  ) {
    items.push({ title: "下发第一项调查任务", description: "选择调查单位和分管范围，生成桌面端任务文件，也可供 Web 在线录入使用。", path: "/tasks", action: "前往任务中心", tone: "blue" });
  }
  if (auth.hasPermission("results.review") && data.pending_package_review_count > 0) {
    items.push({ title: `审核 ${data.pending_package_review_count} 份桌面成果包`, description: "核对成果文件的任务范围和调查内容。", path: "/results?queue=review", action: "前往成果审核", tone: "amber" });
  }
  if (auth.hasPermission("online_entries.review") && data.pending_online_review_count > 0) {
    items.push({ title: `审核 ${data.pending_online_review_count} 条在线调查记录`, description: "检查 Web 录入的调查记录，决定通过入库或退回修改。", path: "/online-reviews", action: "前往在线审核", tone: "amber" });
  }
  if (!items.length) {
    items.push({ title: canReview ? "查看正式成果与审核进度" : "查询正式调查成果", description: "按项目和调查批次查阅已经审核入库的数据及其来源信息。", path: "/central-records", action: "打开正式成果库", tone: "green" });
  }
  return items;
});

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
      <div class="eyebrow">{{ roleTitle }}</div>
      <h1>{{ auth.user?.display_name }}，欢迎使用</h1>
      <p>{{ roleDescription }}</p>
    </div>
    <el-button :icon="Connection" :loading="checking" @click="checkServices">
      刷新运行状态
    </el-button>
  </div>

  <section class="hero-panel hero-aqueduct" :style="heroStyle">
    <div>
      <div class="hero-badge"><span></span> {{ apiState === "online" && dbState === "online" ? "业务服务与资料保存正常" : apiState === "checking" || dbState === "checking" ? "正在检查服务状态" : "部分服务暂时不可用" }}</div>
      <h2>让现场调查有任务、有依据<br />让每份成果可核验、可追溯</h2>
      <p>庄浪河大渡槽 · 中心统一安排，现场离线采集与在线补录协同开展，成果集中管理。</p>
    </div>
    <div class="hero-version">
      <span>当前调查版本</span>
      <strong>{{ overview?.product_version ?? "V1.2.0" }}</strong>
      <small>桌面端与中心端数据标准一致</small>
    </div>
  </section>

  <div class="dashboard-grid">
    <div class="metric-card">
      <div class="metric-icon indigo"><DataBoard /></div>
      <div><span>项目总数</span><strong>{{ overview?.project_count ?? "—" }}</strong><small>已建立的调查项目</small></div>
    </div>
    <div class="metric-card">
      <div class="metric-icon cyan"><Connection /></div>
      <div><span>进行中批次</span><strong>{{ overview?.active_batch_count ?? "—" }}</strong><small>当前有效调查批次</small></div>
    </div>
    <div class="metric-card">
      <div class="metric-icon green"><Files /></div>
      <div><span>正式成果</span><strong>{{ overview?.central_record_count ?? "—" }}</strong><small>{{ auth.hasPermission("results.review") || auth.hasPermission("online_entries.review") ? `${overview?.pending_review_count ?? 0} 个成果待审核` : "可查询已入库记录" }}</small></div>
    </div>
    <div class="metric-card">
      <div class="metric-icon amber"><Document /></div>
      <div><span>调查任务</span><strong>{{ overview?.survey_task_count ?? "—" }}</strong><small>中心已安排的调查工作</small></div>
    </div>
  </div>

  <section class="work-prompts" aria-label="当前建议办理事项">
    <div class="work-prompts-heading">
      <div><span class="eyebrow">按业务顺序推进</span><h2>当前建议先做</h2></div>
      <span>系统根据现有项目、资料、任务和成果自动提示</span>
    </div>
    <div class="work-prompt-grid">
      <router-link v-for="item in workPrompts" :key="`${item.path}-${item.title}`" :to="item.path" class="work-prompt-card" :class="item.tone">
        <span class="work-prompt-dot"></span>
        <div><strong>{{ item.title }}</strong><p>{{ item.description }}</p></div>
        <b>{{ item.action }} →</b>
      </router-link>
    </div>
  </section>

  <el-card shadow="never" class="business-card collaboration-card">
    <template #header>
      <div class="card-header">
        <span>一项调查，三步完成</span>
        <small>Web 与桌面端共同使用一套任务和正式资料</small>
      </div>
    </template>
    <div class="collaboration-flow">
      <div><b>1</b><strong>准备调查</strong><span>维护单位与渠系，建立批次并下发任务</span></div>
      <i>→</i>
      <div><b>2</b><strong>开展录入</strong><span>有网络时在 Web 录入，现场无网络时使用桌面端，同一条记录不重复录入</span></div>
      <i>→</i>
      <div><b>3</b><strong>分别审核入库</strong><span>在线记录和桌面成果包走各自审核入口，通过后汇入同一套正式成果</span></div>
    </div>
    <div class="collaboration-benefits">
      <span>基础资料只维护一次</span>
      <span>干渠也可分段分所管理</span>
      <span>在线录入与离线采集互补</span>
      <span>审核后只保留一套正式成果</span>
    </div>
  </el-card>

  <div class="dashboard-lower">
    <el-card shadow="never" class="business-card service-panel">
      <template #header>
        <div class="card-header"><span>系统运行情况</span><small>出现异常时可刷新检查</small></div>
      </template>
      <div class="service-row">
        <div class="service-status-dot" :class="apiState"></div>
        <div class="service-detail"><strong>业务功能</strong><span>登录、任务和成果处理</span></div>
        <el-tag :type="apiStatusType" effect="light">{{ apiState === "online" ? "运行正常" : apiState === "checking" ? "检测中" : "连接失败" }}</el-tag>
      </div>
      <div class="service-row">
        <div class="service-status-dot" :class="dbState"></div>
        <div class="service-detail"><strong>资料保存</strong><span>中心业务资料安全保存</span></div>
        <el-tag :type="dbStatusType" effect="light">{{ dbState === "online" ? "运行正常" : dbState === "checking" ? "检测中" : "连接失败" }}</el-tag>
      </div>
    </el-card>

    <el-card shadow="never" class="business-card master-panel">
      <template #header>
      <div class="card-header"><span>单位与渠系</span><router-link to="/master-data">{{ auth.hasPermission("master_data.write") ? "前往维护" : "查看资料" }}</router-link></div>
      </template>
      <div class="master-overview">
        <div class="master-orb"><el-icon><OfficeBuilding /></el-icon></div>
        <div class="master-numbers">
          <div><strong>{{ overview?.official_department_count ?? "—" }}</strong><span>管理处</span></div>
          <div><strong>{{ overview?.official_office_count ?? "—" }}</strong><span>管理所</span></div>
          <div><strong>{{ overview?.official_canal_count ?? "—" }}</strong><span>渠道</span></div>
          <div><strong>{{ overview?.official_scope_count ?? "—" }}</strong><span>分管段</span></div>
        </div>
      </div>
      <router-link v-if="overview?.unassigned_backbone_canal_count" class="master-attention" to="/master-data">
        {{ overview.unassigned_backbone_canal_count }} 条骨干渠还没有设置分管所，{{ auth.hasPermission("master_data.write") ? "点击前往补充" : "点击查看详情" }}
      </router-link>
      <div v-else class="version-line">单位、渠系和分管关系已设置完整</div>
    </el-card>
  </div>
</template>
