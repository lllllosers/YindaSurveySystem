<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  getOnlineEntry,
  getOnlineFormDefinitions,
  listOnlineEntries,
  onlineMediaUrl,
  reviewOnlineEntry,
  type FormField,
  type OnlineEntry,
  type OnlineFormDefinition,
} from "../api/onlineEntries";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const rows = ref<OnlineEntry[]>([]);
const definitions = ref<OnlineFormDefinition[]>([]);
const selected = ref<OnlineEntry | null>(null);
const drawerVisible = ref(false);
const loading = ref(false);
const reviewing = ref(false);
const pageNumber = ref(1);
const pageSize = 20;
const total = ref(0);
const pendingCount = ref(0);

const definition = computed(() => definitions.value.find((item) => item.form_code === selected.value?.form_code));
const fieldMap = computed(() => new Map(definition.value?.fields.map((field) => [field.key, field]) ?? []));
const ownEntry = computed(() => !auth.isAdmin && selected.value?.created_by_username === auth.user?.username);

const conclusionFields = [
  ["survey_date", "调查日期"],
  ["overall_grade", "总体评价"],
  ["surveyor_signatures", "调查人员"],
  ["water_office_manager_signature", "水管所负责人"],
  ["engineering_section_chief_signature", "工程科负责人"],
  ["department_head_signature", "管理处负责人"],
  ["survey_comment", "调查意见与建议"],
] as const;

function fieldOf(key: string): FormField | undefined {
  return fieldMap.value.get(key);
}

function displayValue(value: unknown, unit?: string | null): string {
  if (value === null || value === undefined || value === "") return "—";
  const text = Array.isArray(value) ? value.join("、") : typeof value === "object" ? JSON.stringify(value) : String(value);
  return unit ? `${text} ${unit}` : text;
}

function formatTime(value: string | null): string {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—";
}

function openMedia(entryUid: string, mediaUid: string) {
  window.open(onlineMediaUrl(entryUid, mediaUid), "_blank");
}

function errorMessage(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return typeof detail === "string" && detail ? detail : "操作失败，请刷新后重试";
}

async function refresh() {
  loading.value = true;
  try {
    let page = await listOnlineEntries({ status: "submitted", limit: pageSize, offset: (pageNumber.value - 1) * pageSize });
    if (pageNumber.value > 1 && !page.items.length) {
      pageNumber.value = Math.max(1, Math.ceil(page.total / pageSize));
      page = await listOnlineEntries({ status: "submitted", limit: pageSize, offset: (pageNumber.value - 1) * pageSize });
    }
    rows.value = page.items;
    total.value = page.total;
    pendingCount.value = page.summary.submitted;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loading.value = false;
  }
}

async function openDetail(row: OnlineEntry) {
  try {
    selected.value = await getOnlineEntry(row.entry_uid);
    drawerVisible.value = true;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  }
}

async function review(decision: "accept" | "reject") {
  const entry = selected.value;
  if (!entry || reviewing.value) return;
  try {
    let notes: string | null = null;
    if (decision === "reject") {
      const result = await ElMessageBox.prompt(
        "请写明需要补充或修改的内容，录入人员会看到这条意见。",
        "退回在线记录",
        { inputPlaceholder: "填写修改意见", inputValidator: (value) => Boolean(value.trim()) || "请填写修改意见" },
      );
      notes = result.value.trim();
    } else {
      await ElMessageBox.confirm(
        "通过后该记录会立即进入正式成果库。请确认调查内容和影像已经核对。",
        "通过并入库",
        { type: "warning", confirmButtonText: "确认通过" },
      );
    }
    reviewing.value = true;
    await reviewOnlineEntry(entry.entry_uid, decision, notes);
    drawerVisible.value = false;
    ElMessage.success(decision === "accept" ? "审核通过，已进入正式成果库" : "已退回录入人员修改");
    await refresh();
  } catch (error) {
    if (error !== "cancel" && error !== "close") ElMessage.error(errorMessage(error));
  } finally {
    reviewing.value = false;
  }
}

async function changePage(page: number) {
  pageNumber.value = page;
  await refresh();
}

onMounted(async () => {
  await Promise.all([
    refresh(),
    getOnlineFormDefinitions().then((items) => { definitions.value = items; }).catch((error) => ElMessage.error(errorMessage(error))),
  ]);
});
</script>

<template>
  <div class="module-header">
    <div>
      <div class="eyebrow">独立审核队列 · 在线填报</div>
      <h1>在线记录审核</h1>
      <p>逐条核对在线录入的调查内容；通过后直接进入正式成果库，退回后由录入人员修改。</p>
    </div>
    <el-button :loading="loading" @click="refresh">刷新待办</el-button>
  </div>

  <el-alert class="linkage-alert" type="info" :closable="false" show-icon title="这里仅处理 Web 在线提交的记录。桌面端成果包在“成果包审核”中完成文件核验、接收和入库。" />

  <el-card shadow="never" class="business-card">
    <template #header><div class="card-header"><span>待审核在线记录</span><el-tag type="warning">{{ pendingCount }} 条</el-tag></div></template>
    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column label="调查对象" min-width="190"><template #default="{ row }"><strong>{{ row.asset_name || "未命名调查对象" }}</strong><div class="result-secondary">{{ row.form_name }}</div></template></el-table-column>
      <el-table-column label="所属任务和批次" min-width="220"><template #default="{ row }">{{ row.task_name }}<div class="result-secondary">{{ row.project_name }} · {{ row.batch_name }}</div></template></el-table-column>
      <el-table-column label="范围与单位" min-width="190"><template #default="{ row }">{{ row.canal_name }}<div class="result-secondary">{{ row.organization_name }}</div></template></el-table-column>
      <el-table-column prop="created_by_username" label="录入人" width="115" />
      <el-table-column label="提交时间" width="185"><template #default="{ row }">{{ formatTime(row.submitted_at) }}</template></el-table-column>
      <el-table-column label="操作" width="120" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openDetail(row)">查看并审核</el-button></template></el-table-column>
      <template #empty><el-empty description="目前没有待审核的在线记录" /></template>
    </el-table>
    <el-pagination v-if="total > pageSize" v-model:current-page="pageNumber" :page-size="pageSize" :total="total" layout="total, prev, pager, next" class="entry-pagination" @current-change="changePage" />
  </el-card>

  <el-drawer v-model="drawerVisible" title="在线记录审核" size="78%">
    <template v-if="selected">
      <div class="task-detail-hero"><el-tag type="warning">待审核</el-tag><h2>{{ selected.asset_name || "未命名调查对象" }}</h2><p>{{ selected.form_name }}</p></div>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="所属任务" :span="2">{{ selected.task_name }}</el-descriptions-item>
        <el-descriptions-item label="项目批次" :span="2">{{ selected.project_name }} · {{ selected.batch_name }}</el-descriptions-item>
        <el-descriptions-item label="管理单位">{{ selected.organization_name }}</el-descriptions-item>
        <el-descriptions-item label="渠道">{{ selected.canal_name }}</el-descriptions-item>
        <el-descriptions-item label="录入人">{{ selected.created_by_username }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ formatTime(selected.submitted_at) }}</el-descriptions-item>
      </el-descriptions>

      <template v-if="definition">
        <section v-for="section in definition.sections" :key="section.title" class="online-review-section">
          <h3>{{ section.title }}</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item v-for="fieldKey in section.rows.flatMap((row) => row.field_keys)" :key="fieldKey" :label="fieldOf(fieldKey)?.display_label || fieldKey">
              {{ displayValue(selected.form_data[fieldKey], fieldOf(fieldKey)?.unit) }}
            </el-descriptions-item>
          </el-descriptions>
        </section>
      </template>
      <section class="online-review-section">
        <h3>评价项目</h3>
        <el-table :data="selected.evaluations" stripe border>
          <el-table-column prop="item_name" label="项目" min-width="170" />
          <el-table-column prop="grade" label="等级" width="100" />
          <el-table-column prop="description" label="现场情况" min-width="200" />
          <el-table-column prop="remark" label="备注" min-width="150" />
        </el-table>
      </section>
      <section class="online-review-section">
        <h3>调查结论</h3>
        <el-descriptions :column="2" border>
          <el-descriptions-item v-for="[key, label] in conclusionFields" :key="key" :label="label" :span="key === 'survey_comment' ? 2 : 1">{{ displayValue(selected.conclusion[key]) }}</el-descriptions-item>
        </el-descriptions>
      </section>
      <section class="online-review-section">
        <h3>现场影像（{{ selected.media.length }}）</h3>
        <div v-if="selected.media.length" class="entry-media-list">
          <div v-for="media in selected.media" :key="media.media_uid" class="entry-media-item">
            <span class="entry-media-kind">{{ media.media_kind === "photo" ? "照片" : "视频" }}</span>
            <div><strong>{{ media.original_filename }}</strong><small>{{ media.media_role }}{{ media.part_name ? ` · ${media.part_name}` : "" }}</small></div>
            <el-button link type="primary" @click="openMedia(selected.entry_uid, media.media_uid)">查看影像</el-button>
          </div>
        </div>
        <el-empty v-else description="未附现场影像" :image-size="54" />
      </section>
      <el-alert v-if="ownEntry" type="warning" title="本人录入的记录需由其他审核人员处理。" :closable="false" show-icon />
    </template>
    <template #footer>
      <el-button @click="drawerVisible = false">关闭</el-button>
      <el-button :disabled="ownEntry || selected?.status !== 'submitted'" :loading="reviewing" @click="review('reject')">退回修改</el-button>
      <el-button type="primary" :disabled="ownEntry || selected?.status !== 'submitted'" :loading="reviewing" @click="review('accept')">通过并入库</el-button>
    </template>
  </el-drawer>
</template>
