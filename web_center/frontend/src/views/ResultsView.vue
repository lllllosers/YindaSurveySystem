<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ElMessage,
  ElMessageBox,
  type UploadFile,
  type UploadRawFile,
} from "element-plus";

import {
  deleteResultSubmission,
  listResultSubmissions,
  preflightResultSubmission,
  resultDownloadUrl,
  uploadResultPackage,
  type ResultSubmission,
  type ResultSubmissionSummary,
} from "../api/results";
import { listProjects, listSurveyBatches, type Project, type SurveyBatch } from "../api/projects";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();

const loading = ref(false);
const uploading = ref(false);
const rows = ref<ResultSubmission[]>([]);
const selectedForPreflight = ref<ResultSubmission[]>([]);
const preflightBusy = ref(false);
const preflightProgress = ref(0);
const preflightTotal = ref(0);
const uploadFiles = ref<UploadFile[]>([]);
type ResultQueue = "check" | "review" | "import" | "attention";
const initialQueue = ["check", "review", "import", "attention"].includes(String(route.query.queue)) ? route.query.queue as ResultQueue : "";
const queueFilter = ref<ResultQueue | "">(initialQueue);
const statusFilter = ref(initialQueue ? "" : typeof route.query.status === "string" ? route.query.status : "");
const keyword = ref("");
const projectUid = ref("");
const batchUid = ref("");
const projects = ref<Project[]>([]);
const batches = ref<SurveyBatch[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);
const summary = ref<ResultSubmissionSummary>({
  total: 0,
  awaiting_check: 0,
  awaiting_review: 0,
  needs_attention: 0,
  accepted: 0,
  imported: 0,
});

const canUpload = computed(
  () => auth.hasPermission("results.upload"),
);
const deletableStatuses = new Set(["uploaded", "inspected", "invalid", "conflict"]);

async function removeSubmission(row: ResultSubmission) {
  try {
    await ElMessageBox.confirm(`删除“${row.result_name || row.original_filename}”及其上传文件？`, "删除成果包", { type: "warning", confirmButtonText: "删除" });
    await deleteResultSubmission(row.submission_uid);
    ElMessage.success("成果包已删除");
    await refresh();
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error?.response?.data?.detail || "成果包删除失败");
  }
}
const canPreflight = computed(() => auth.hasPermission("results.preflight"));
const selectedFiles = computed(() => uploadFiles.value
  .map((item) => item.raw)
  .filter((item): item is UploadRawFile => item !== undefined));

const statusLabels: Record<string, string> = {
  uploaded: "已上传",
  inspected: "文件检查通过",
  invalid: "文件检查未通过",
  preflight_passed: "业务核验通过",
  conflict: "需要处理",
  reviewing: "审核中",
  accepted: "已接收",
  rejected: "已退回",
  imported: "已入库",
};

const storageLabels: Record<string, string> = {
  unchecked: "尚未复查",
  ok: "完整",
  missing: "文件缺失",
  size_mismatch: "大小异常",
  hash_mismatch: "文件内容异常",
  package_invalid: "成果文件异常",
  error: "检查异常",
};

function statusType(status: string) {
  if (
    ["inspected", "preflight_passed", "accepted", "imported"]
      .includes(status)
  ) {
    return "success";
  }

  if (
    ["invalid", "conflict", "rejected"]
      .includes(status)
  ) {
    return "danger";
  }

  return "info";
}

function storageType(status: string) {
  if (status === "ok") return "success";
  if (status === "unchecked") return "info";
  return "danger";
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  if (value < 1024 ** 3) {
    return `${(value / 1024 ** 2).toFixed(1)} MB`;
  }
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function formatTime(value: string) {
  return new Date(value).toLocaleString(
    "zh-CN",
    { hour12: false },
  );
}

function uploadErrorMessage(error: any): string {
  const status = error?.response?.status;
  if (status === 413) return "成果文件过大，请检查后重新选择";
  if (status === 409) return "这份成果已经上传，或与现有成果重复，请核对后再试";
  if (status === 400 || status === 422) return "成果文件无法识别，请从桌面端重新导出后上传";
  return "成果上传失败，请稍后重试；如问题持续，请联系系统管理员";
}

async function refresh() {
  loading.value = true;
  try {
    const data = await listResultSubmissions({
      status: statusFilter.value || undefined,
      queue: queueFilter.value || undefined,
      project_uid: projectUid.value || undefined,
      survey_batch_uid: batchUid.value || undefined,
      keyword: keyword.value.trim() || undefined,
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value,
    });
    rows.value = data.items;
    total.value = data.total;
    summary.value = data.summary;
  } catch {
    ElMessage.error("成果台账加载失败，请稍后重试");
  } finally {
    loading.value = false;
  }
}

async function loadInitial() {
  try {
    projects.value = await listProjects();
  } catch {
    ElMessage.error("项目资料加载失败");
  }
  await refresh();
}

async function onProjectChange() {
  batchUid.value = "";
  batches.value = projectUid.value ? await listSurveyBatches(projectUid.value) : [];
  currentPage.value = 1;
  await refresh();
}

async function applyFilters() {
  currentPage.value = 1;
  await refresh();
}

async function changeStatus() {
  queueFilter.value = "";
  await router.replace({ query: statusFilter.value ? { status: statusFilter.value } : {} });
  await applyFilters();
}

async function chooseQueue(queue: ResultQueue | "") {
  queueFilter.value = queue;
  statusFilter.value = "";
  await router.replace({ query: queue ? { queue } : {} });
  await applyFilters();
}

async function preflightSelected() {
  const selected = [...selectedForPreflight.value];
  if (!selected.length || preflightBusy.value) return;
  preflightBusy.value = true;
  preflightProgress.value = 0;
  preflightTotal.value = selected.length;
  let passed = 0;
  let needsAttention = 0;
  let failed = 0;
  for (const item of selected) {
    try {
      const result = await preflightResultSubmission(item.submission_uid);
      if (result.status === "preflight_passed") passed += 1;
      else needsAttention += 1;
    } catch {
      failed += 1;
    } finally {
      preflightProgress.value += 1;
    }
  }
  preflightBusy.value = false;
  selectedForPreflight.value = [];
  await refresh();
  const message = `核验完成：${passed} 份通过，${needsAttention} 份需处理${failed ? `，${failed} 份失败` : ""}`;
  if (failed || needsAttention) ElMessage.warning(message);
  else ElMessage.success(message);
}

async function clearFilters() {
  keyword.value = "";
  projectUid.value = "";
  batchUid.value = "";
  statusFilter.value = "";
  queueFilter.value = "";
  await router.replace({ query: {} });
  batches.value = [];
  currentPage.value = 1;
  await refresh();
}

async function changePage(page: number) {
  currentPage.value = page;
  await refresh();
}

async function changePageSize(size: number) {
  pageSize.value = size;
  currentPage.value = 1;
  await refresh();
}

function fileChanged(uploadFile: UploadFile) {
  const raw = uploadFile.raw ?? null;

  if (
    raw
    && !raw.name.toLowerCase().endsWith(".ydresult")
  ) {
    ElMessage.error(
      "请选择由桌面端导出的成果文件",
    );
    uploadFiles.value = uploadFiles.value.filter((item) => item.uid !== uploadFile.uid);
    return;
  }
}

function openDetail(row: ResultSubmission) {
  void router.push({
    path: `/results/${row.submission_uid}`,
    query: queueFilter.value ? { queue: queueFilter.value } : statusFilter.value ? { status: statusFilter.value } : {},
  });
}

function download(row: ResultSubmission) {
  window.open(
    resultDownloadUrl(row.submission_uid),
    "_blank",
  );
}

async function upload() {
  if (!selectedFiles.value.length) {
    return;
  }

  uploading.value = true;
  let success = 0;
  let needsAttention = 0;
  let failed = 0;
  for (const file of selectedFiles.value) {
    try {
      const row = await uploadResultPackage(file);
      success += 1;
      if (row.status !== "inspected") needsAttention += 1;
    } catch (error: any) {
      failed += 1;
      ElMessage.error(`${file.name}：${uploadErrorMessage(error)}`);
    }
  }
  uploading.value = false;
  uploadFiles.value = [];
  if (success) {
    ElMessage.success(`已接收 ${success} 份成果文件${needsAttention ? `，其中 ${needsAttention} 份需要核对` : ""}${failed ? `，${failed} 份未接收` : ""}`);
  }
  await refresh();
}

onMounted(loadInitial);
</script>

<template>
  <div class="module-header">
    <div>
      <div class="eyebrow">桌面端成果回收</div>
      <h1>{{ canUpload ? "成果接收与审核" : auth.hasPermission("results.review") ? "成果审核" : "成果台账" }}</h1>
      <p>
        {{ canUpload ? "上传桌面端导出的调查成果，系统自动核对任务范围，审核通过后统一进入成果库。" : auth.hasPermission("results.review") ? "查看桌面端成果的核验情况，审核待处理成果。" : "查看成果回收和入库进度。" }}
      </p>
    </div>
  </div>

  <el-alert
    v-if="canUpload"
    class="linkage-alert"
    title="与桌面端联动：现场调查人员在桌面端完成记录并选择“成果提交”，将导出的成果文件交回中心，在本页上传、核验和审核。无需重复抄表或人工合并。"
    type="success"
    :closable="false"
    show-icon
  />

  <el-alert v-if="canUpload" class="task-handover-alert" type="info" :closable="false" show-icon>
    <template #title>
      回收以前由桌面端下发任务形成的成果时，请先到
      <router-link to="/tasks">任务下发</router-link>
      登记原始任务文件，再批量上传成果；项目、批次和历史调查范围会自动接续，无需重做。
    </template>
  </el-alert>

  <div class="result-stat-row">
    <div><span>成果总数</span><strong>{{ summary.total }}</strong></div>
    <div><span>待业务核验</span><strong>{{ summary.awaiting_check }}</strong></div>
    <div><span>待审核</span><strong>{{ summary.awaiting_review }}</strong></div>
    <div><span>需要处理</span><strong>{{ summary.needs_attention }}</strong></div>
    <div><span>待正式入库</span><strong>{{ summary.accepted }}</strong></div>
    <div><span>已正式入库</span><strong>{{ summary.imported }}</strong></div>
  </div>

  <el-card
    v-if="canUpload"
    shadow="never"
    class="business-card result-upload-card"
  >
    <template #header>
      <div class="card-header">
        <span>上传桌面端调查成果</span>
        <el-tag
          type="info"
          effect="plain"
        >
          桌面端成果文件
        </el-tag>
      </div>
    </template>

    <div class="result-upload-row">
      <el-upload
        v-model:file-list="uploadFiles"
        :auto-upload="false"
        :limit="50"
        multiple
        accept=".ydresult"
        @change="fileChanged"
      >
        <el-button>批量选择成果文件</el-button>
      </el-upload>

      <el-button
        type="primary"
        :loading="uploading"
        :disabled="!selectedFiles.length"
        @click="upload"
      >
        上传并核对（{{ selectedFiles.length }}）
      </el-button>
    </div>
  </el-card>

  <el-card
    shadow="never"
    class="business-card result-list-card"
  >
    <template #header>
      <div class="result-queue-bar">
        <el-button :type="queueFilter === '' ? 'primary' : 'default'" @click="chooseQueue('')">全部 {{ summary.total }}</el-button>
        <el-button :type="queueFilter === 'check' ? 'primary' : 'default'" @click="chooseQueue('check')">待核验 {{ summary.awaiting_check }}</el-button>
        <el-button v-if="auth.hasPermission('results.review')" :type="queueFilter === 'review' ? 'primary' : 'default'" @click="chooseQueue('review')">待审核 {{ summary.awaiting_review }}</el-button>
        <el-button v-if="auth.hasPermission('results.import')" :type="queueFilter === 'import' ? 'primary' : 'default'" @click="chooseQueue('import')">待入库 {{ summary.accepted }}</el-button>
        <el-button :type="queueFilter === 'attention' ? 'primary' : 'default'" @click="chooseQueue('attention')">需处理 {{ summary.needs_attention }}</el-button>
        <el-button v-if="canPreflight" :disabled="!selectedForPreflight.length || preflightBusy" :loading="preflightBusy" @click="preflightSelected">
          {{ preflightBusy ? `正在核验 ${preflightProgress}/${preflightTotal}` : `批量业务核验（${selectedForPreflight.length}）` }}
        </el-button>
      </div>
      <div class="card-header">
        <div class="result-ledger-title">
          <span>成果协同台账</span>
          <small>共 {{ total }} 条符合当前条件</small>
        </div>

        <div class="result-filter">
          <el-input
            v-model="keyword"
            clearable
            placeholder="成果名称、文件名或上传人"
            style="width: 230px"
            @keyup.enter="applyFilters"
            @clear="applyFilters"
          />
          <el-select
            v-model="projectUid"
            clearable
            placeholder="全部项目"
            style="width: 180px"
            @change="onProjectChange"
          >
            <el-option v-for="item in projects" :key="item.project_uid" :label="item.name" :value="item.project_uid" />
          </el-select>
          <el-select
            v-model="batchUid"
            clearable
            placeholder="全部批次"
            style="width: 170px"
            :disabled="!projectUid"
            @change="applyFilters"
          >
            <el-option v-for="item in batches" :key="item.survey_batch_uid" :label="item.batch_name" :value="item.survey_batch_uid" />
          </el-select>
          <el-select
            v-model="statusFilter"
            clearable
            placeholder="全部状态"
            style="width: 180px"
            @change="changeStatus"
          >
            <el-option
              label="文件检查通过"
              value="inspected"
            />
            <el-option
              label="文件检查未通过"
              value="invalid"
            />
            <el-option
              label="需要处理"
              value="conflict"
            />
            <el-option
              label="业务核验通过"
              value="preflight_passed"
            />
            <el-option
              label="审核中"
              value="reviewing"
            />
            <el-option
              label="已接收"
              value="accepted"
            />
            <el-option
              label="已退回"
              value="rejected"
            />
            <el-option
              label="已入库"
              value="imported"
            />
          </el-select>

          <el-button type="primary" @click="applyFilters">查询</el-button>
          <el-button v-if="keyword || projectUid || batchUid || statusFilter" @click="clearFilters">清空</el-button>
          <el-button @click="refresh">刷新</el-button>
        </div>
      </div>
    </template>

    <el-table
      v-loading="loading"
      :data="rows"
      @selection-change="(selected: ResultSubmission[]) => { if (!preflightBusy) selectedForPreflight = selected; }"
    >
      <el-table-column v-if="canPreflight" type="selection" width="48" :selectable="(item: ResultSubmission) => !preflightBusy && item.status !== 'imported'" />
      <el-table-column
        label="上传时间"
        width="185"
      >
        <template #default="{ row }">
          {{ formatTime(row.uploaded_at) }}
        </template>
      </el-table-column>

      <el-table-column
        label="成果"
        min-width="220"
      >
        <template #default="{ row }">
          <div>
            {{ row.result_name || row.original_filename }}
          </div>
          <div class="result-secondary">
            {{ row.project_name || "未匹配项目" }} · {{ row.survey_batch_name || "未匹配批次" }}
          </div>
        </template>
      </el-table-column>

      <el-table-column
        label="提交状态"
        width="140"
      >
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">
            {{ statusLabels[row.status] || "状态待确认" }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column
        label="文件状态"
        width="125"
      >
        <template #default="{ row }">
          <el-tag :type="storageType(row.storage_status)">
            {{
              storageLabels[row.storage_status]
                || "状态待确认"
            }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column
        label="记录"
        width="80"
      >
        <template #default="{ row }">
          {{ row.counts.survey_records ?? "—" }}
        </template>
      </el-table-column>

      <el-table-column
        label="影像"
        width="80"
      >
        <template #default="{ row }">
          {{ row.counts.survey_media ?? "—" }}
        </template>
      </el-table-column>

      <el-table-column
        label="大小"
        width="110"
      >
        <template #default="{ row }">
          {{ formatBytes(row.file_size) }}
        </template>
      </el-table-column>

      <el-table-column
        prop="uploader_username"
        label="上传人"
        width="120"
      />

      <el-table-column
        label="检查"
        min-width="180"
      >
        <template #default="{ row }">
          <span
            v-if="row.inspection_error_count === 0"
          >
            文件内容完整
          </span>

          <el-popover
            v-else
            placement="top"
            :width="420"
            trigger="hover"
          >
            <template #reference>
              <el-text type="danger">
                {{ row.inspection_error_count }} 个问题
              </el-text>
            </template>

            <div class="result-issue">
              成果文件存在无法读取的内容，请从桌面端重新导出后上传。
            </div>
          </el-popover>
        </template>
      </el-table-column>

      <el-table-column
        label="操作"
        width="190"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button
            link
            type="primary"
            @click="openDetail(row)"
          >
            详情
          </el-button>

          <el-button
            link
            @click="download(row)"
          >
            下载
          </el-button>
          <el-button v-if="canUpload && deletableStatuses.has(row.status)" link type="danger" @click="removeSubmission(row)">删除</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="business-empty compact">
          <div class="business-empty-mark">审</div>
          <h3>{{ queueFilter === 'review' ? '没有待审核的成果包' : queueFilter === 'import' ? '没有待入库的成果包' : '当前条件下没有成果包' }}</h3>
          <p>可调整上方筛选条件。现场人员从桌面端导出成果文件后，由中心上传并核对。</p>
        </div>
      </template>
    </el-table>
    <div class="result-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @current-change="changePage"
        @size-change="changePageSize"
      />
    </div>
  </el-card>
</template>

<style scoped>
.result-queue-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.result-queue-bar :deep(.el-button + .el-button) {
  margin-left: 0;
}

.result-stat-row {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  margin: 16px 0;
}

.result-stat-row > div {
  padding: 16px 18px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px;
  background: var(--el-bg-color);
}

.result-stat-row span,
.result-stat-row strong {
  display: block;
}

.result-stat-row span {
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.result-stat-row strong {
  margin-top: 5px;
  font-size: 25px;
}

.result-ledger-title {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.result-ledger-title small {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  font-weight: 400;
}

.result-filter {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.result-pagination {
  display: flex;
  justify-content: flex-end;
  padding-top: 18px;
}

@media (max-width: 1180px) {
  .result-stat-row {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .result-stat-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
