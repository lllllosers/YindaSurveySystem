<script setup lang="ts">
import {
  computed,
  onMounted,
  ref,
} from "vue";
import {
  useRoute,
  useRouter,
} from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  getResultSubmission,
  importResultSubmission,
  preflightResultSubmission,
  resultDownloadUrl,
  reviewResultSubmission,
  verifyResultSubmission,
  type ResultFileVerification,
  type ResultSubmission,
} from "../api/results";
import { useAuthStore } from "../stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const loading = ref(false);
const verifying = ref(false);
const workflowBusy = ref(false);
const row = ref<ResultSubmission | null>(null);
const verification = ref<ResultFileVerification | null>(null);

const submissionUid = computed(
  () => String(route.params.submissionUid ?? ""),
);

const canVerify = computed(
  () => auth.hasPermission("results.verify"),
);
const canPreflight = computed(
  () => auth.hasPermission("results.preflight"),
);
const canReview = computed(
  () => auth.hasPermission("results.review"),
);
const canImport = computed(
  () => auth.hasPermission("results.import"),
);

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
  size_mismatch: "大小不一致",
  hash_mismatch: "文件内容发生变化",
  package_invalid: "成果文件异常",
  error: "检查异常",
};

function storageTagType(status: string) {
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

function formatTime(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString(
    "zh-CN",
    { hour12: false },
  );
}

function actionErrorMessage(error: any, fallback: string) {
  const status = error?.response?.status;
  if (status === 403) return "当前账户没有执行这项操作的权限";
  if (status === 404) return "没有找到这份成果，可能已被移交或状态已更新";
  if (status === 409) return `${fallback}，请刷新页面并确认当前处理状态`;
  return `${fallback}，请稍后重试`;
}

function workflowIssueText(issue: ResultSubmission["preflight_issues"][number]) {
  const code = issue.code;
  if (code.startsWith("PROTOCOL_")) {
    return "成果文件与当前桌面端数据标准不一致，请由桌面端升级到最新版本后重新导出。";
  }
  if (code === "STRUCTURE_CHECK_REQUIRED") return "成果文件检查未通过，请先处理文件问题。";
  if (code.startsWith("SUBMISSION_TASK_")) return "没有找到本次成果对应的有效调查任务，请核对任务后重新提交。";
  if (code.includes("PROJECT") || code.includes("BATCH")) return "成果所属项目或调查批次与中心安排不一致，请核对后重新提交。";
  if (code.includes("SCOPE")) return "部分调查记录超出本次安排的调查范围，请在桌面端核对后重新导出。";
  if (code.includes("SOURCE_TASK")) return "部分调查记录缺少正确的任务来源，请在桌面端核对后重新导出。";
  if (code.includes("FORM")) return "成果中包含本次任务未安排的调查表，请核对后重新提交。";
  if (code.includes("NOT_COMPLETED")) return "成果中包含尚未完成的调查记录，请在桌面端完成后重新导出。";
  if (code.includes("STALE") || code.includes("REVISION_CONFLICT")) return "中心已有更新的调查内容，请核对最新成果后再提交。";
  return issue.severity === "error"
    ? "发现需要处理的调查内容，请回到桌面端核对后重新提交。"
    : "发现需要关注的调查内容，请审核人员核实。";
}

function fileIssueText(issue: ResultSubmission["inspection_issues"][number]) {
  if (issue.code.includes("HASH")) return "成果文件内容与导出时不一致，请从桌面端重新导出后上传。";
  if (issue.code.includes("ZIP") || issue.code.includes("ARCHIVE")) return "成果文件无法正常打开，请从桌面端重新导出。";
  if (issue.code.includes("MANIFEST")) return "成果文件的清单信息不完整，请从桌面端重新导出。";
  return "成果文件存在无法读取的内容，请从桌面端重新导出后上传。";
}

async function refresh() {
  loading.value = true;

  try {
    row.value = await getResultSubmission(
      submissionUid.value,
    );
  } catch (error: any) {
    ElMessage.error(actionErrorMessage(error, "成果详情读取失败"));
  } finally {
    loading.value = false;
  }
}

async function verifyFile() {
  verifying.value = true;

  try {
    verification.value = (
      await verifyResultSubmission(
        submissionUid.value,
      )
    );

    await refresh();

    if (
      verification.value.storage_status === "ok"
    ) {
      ElMessage.success(
        "成果文件保管检查通过",
      );
    } else {
      ElMessage.warning(
        "成果文件可能缺失或发生变化，请重新取得桌面端原文件",
      );
    }
  } catch (error: any) {
    ElMessage.error(actionErrorMessage(error, "成果文件检查失败"));
  } finally {
    verifying.value = false;
  }
}

async function runPreflight() {
  workflowBusy.value = true;
  try {
    row.value = await preflightResultSubmission(submissionUid.value);
    if (row.value.preflight_error_count === 0) {
      ElMessage.success("业务核验通过，可以进入审核");
    } else {
      ElMessage.warning(`业务核验发现 ${row.value.preflight_error_count} 个需要处理的问题`);
    }
  } catch (error: any) {
    ElMessage.error(actionErrorMessage(error, "业务核验失败"));
  } finally {
    workflowBusy.value = false;
  }
}

async function review(decision: "accepted" | "rejected") {
  let notes: string | null = null;
  try {
    const action = decision === "accepted" ? "接收" : "退回";
    const result = await ElMessageBox.prompt(
      `请填写${action}意见（可以留空）`,
      `审核${action}`,
      {
        confirmButtonText: `确认${action}`,
        cancelButtonText: "取消",
        inputType: "textarea",
        inputPlaceholder: "审核意见",
      },
    );
    notes = result.value?.trim() || null;
  } catch {
    return;
  }
  workflowBusy.value = true;
  try {
    row.value = await reviewResultSubmission(submissionUid.value, decision, notes);
    ElMessage.success(decision === "accepted" ? "成果已审核接收" : "成果已退回");
  } catch (error: any) {
    ElMessage.error(actionErrorMessage(error, "成果审核失败"));
  } finally {
    workflowBusy.value = false;
  }
}

async function importResult() {
  try {
    await ElMessageBox.confirm(
      "入库前系统会再次核对调查范围和数据版本。确认将该成果纳入正式成果库？",
      "正式入库",
      { confirmButtonText: "确认入库", cancelButtonText: "取消", type: "warning" },
    );
  } catch {
    return;
  }
  workflowBusy.value = true;
  try {
    const result = await importResultSubmission(submissionUid.value);
    await refresh();
    ElMessage.success(`入库完成：${result.records} 条调查记录`);
  } catch (error: any) {
    ElMessage.error(actionErrorMessage(error, "成果入库失败"));
  } finally {
    workflowBusy.value = false;
  }
}

function download() {
  window.open(
    resultDownloadUrl(submissionUid.value),
    "_blank",
  );
}

function back() {
  void router.push("/results");
}

onMounted(refresh);
</script>

<template>
  <div class="module-header">
    <div>
      <div class="eyebrow">成果质量核验</div>
      <h1>成果审核详情</h1>
      <p>
        核对成果来源和调查范围，审核通过后纳入正式成果库。
      </p>
    </div>

    <div class="detail-actions">
      <el-button @click="back">
        返回成果列表
      </el-button>

      <el-button @click="download">
        下载成果文件
      </el-button>

      <el-button
        v-if="canVerify"
        type="primary"
        :loading="verifying"
        @click="verifyFile"
      >
        重新检查文件
      </el-button>

      <el-button
        v-if="canPreflight && row?.status !== 'imported'"
        :loading="workflowBusy"
        @click="runPreflight"
      >
        核对业务内容
      </el-button>

      <el-button
        v-if="canReview && row?.status === 'preflight_passed'"
        type="success"
        :loading="workflowBusy"
        @click="review('accepted')"
      >
        审核接收
      </el-button>

      <el-button
        v-if="canReview && row && !['imported', 'rejected'].includes(row.status)"
        type="danger"
        plain
        :loading="workflowBusy"
        @click="review('rejected')"
      >
        退回
      </el-button>

      <el-button
        v-if="canImport && row?.status === 'accepted'"
        type="primary"
        :loading="workflowBusy"
        @click="importResult"
      >
        正式入库
      </el-button>
    </div>
  </div>

  <div v-loading="loading">
    <template v-if="row">
      <el-card
        shadow="never"
        class="business-card detail-card"
      >
        <template #header>
          <div class="card-header">
            <span>
              {{ row.result_name || row.original_filename }}
            </span>

            <div class="detail-tags">
              <el-tag>
                {{ statusLabels[row.status] || "状态待确认" }}
              </el-tag>

              <el-tag
                :type="storageTagType(row.storage_status)"
              >
                {{
                  storageLabels[row.storage_status]
                  || "状态待确认"
                }}
              </el-tag>
            </div>
          </div>
        </template>

        <el-descriptions
          :column="2"
          border
        >
          <el-descriptions-item label="所属项目">
            {{ row.project_name || "未匹配到中心项目" }}
          </el-descriptions-item>

          <el-descriptions-item label="调查批次">
            {{ row.survey_batch_name || "未匹配到中心批次" }}
          </el-descriptions-item>

          <el-descriptions-item label="提交单位">
            {{ row.submission_unit_name || "未识别" }}
          </el-descriptions-item>

          <el-descriptions-item label="对应任务">
            {{ row.submission_task_name || "未识别中心下发任务" }}
          </el-descriptions-item>

          <el-descriptions-item label="上传人">
            {{ row.uploader_username }}
          </el-descriptions-item>

          <el-descriptions-item label="上传时间">
            {{ formatTime(row.uploaded_at) }}
          </el-descriptions-item>

          <el-descriptions-item label="文件大小">
            {{ formatBytes(row.file_size) }}
          </el-descriptions-item>

          <el-descriptions-item label="桌面端软件">
            {{
              row.desktop_app_version_label
                || row.desktop_app_version
                || "—"
            }}
          </el-descriptions-item>

          <el-descriptions-item label="调查记录数">
            {{ row.counts.survey_records ?? "—" }}
          </el-descriptions-item>

          <el-descriptions-item label="影像数">
            {{ row.counts.survey_media ?? "—" }}
          </el-descriptions-item>

          <el-descriptions-item label="最近检查时间">
            {{ formatTime(row.storage_checked_at) }}
          </el-descriptions-item>

          <el-descriptions-item label="文件状态">
            {{
              storageLabels[row.storage_status]
                || "状态待确认"
            }}
          </el-descriptions-item>
        </el-descriptions>

      </el-card>

      <el-card
        shadow="never"
        class="business-card detail-card"
      >
        <template #header>
          <div class="card-header">
            <span>业务核验与审核</span>
            <small>{{ formatTime(row.preflight_checked_at) }}</small>
          </div>
        </template>

        <el-empty
          v-if="!row.preflight_checked_at"
          description="尚未核对任务范围和调查内容"
        />

        <template v-else>
          <div class="workflow-metrics">
            <div><span>新增工程</span><strong>{{ row.preflight_summary.new_assets ?? 0 }}</strong></div>
            <div><span>新增记录</span><strong>{{ row.preflight_summary.new_records ?? 0 }}</strong></div>
            <div><span>更新记录</span><strong>{{ row.preflight_summary.updated_records ?? 0 }}</strong></div>
            <div><span>需处理</span><strong class="danger-text">{{ row.preflight_error_count }}</strong></div>
            <div><span>需关注</span><strong>{{ row.preflight_warning_count }}</strong></div>
          </div>

          <el-alert
            v-if="row.preflight_error_count === 0"
            type="success"
            :closable="false"
            title="调查单位、任务范围、渠道归属和数据版本均已核对通过"
          />

          <div
            v-for="issue in row.preflight_issues"
            :key="`${issue.code}-${issue.entity_uid}`"
            class="detail-issue"
          >
            <el-tag :type="issue.severity === 'error' ? 'danger' : 'warning'" size="small">
              {{ issue.severity === "error" ? "需处理" : "需关注" }}
            </el-tag>
            {{ workflowIssueText(issue) }}
          </div>

          <el-descriptions v-if="row.reviewed_at" :column="2" border class="review-description">
            <el-descriptions-item label="审核人">{{ row.reviewed_by_username || "—" }}</el-descriptions-item>
            <el-descriptions-item label="审核时间">{{ formatTime(row.reviewed_at) }}</el-descriptions-item>
            <el-descriptions-item label="审核意见" :span="2">{{ row.review_notes || "无" }}</el-descriptions-item>
            <el-descriptions-item v-if="row.imported_at" label="正式入库时间" :span="2">
              {{ formatTime(row.imported_at) }}
            </el-descriptions-item>
          </el-descriptions>
        </template>
      </el-card>

      <el-card
        shadow="never"
        class="business-card detail-card"
      >
        <template #header>
          调查来源
        </template>

        <el-empty
          v-if="row.source_task_uids.length === 0"
          description="未找到桌面端调查任务来源，业务核验时会提醒处理"
        />

        <div v-else class="source-summary">
          <strong>{{ row.source_task_uids.length }} 个基层调查任务</strong>
          <span>桌面端保留每条记录的真实调查来源，中心汇总时不会改写原始责任单位。</span>
        </div>
      </el-card>

      <el-card
        shadow="never"
        class="business-card detail-card"
      >
        <template #header>
          上传时文件检查
        </template>

        <el-result
          v-if="row.inspection_error_count === 0"
          icon="success"
          title="文件检查通过"
          sub-title="成果文件完整，可以继续核对调查范围和业务内容。"
        />

        <div v-else>
          <el-alert
            type="error"
            :closable="false"
            :title="`发现 ${row.inspection_error_count} 个问题`"
          />

          <div
            v-for="issue in row.inspection_issues"
            :key="`${issue.code}-${issue.path}`"
            class="detail-issue"
          >
            {{ fileIssueText(issue) }}
          </div>
        </div>
      </el-card>

      <el-card
        v-if="verification"
        shadow="never"
        class="business-card detail-card"
      >
        <template #header>
          本次文件保管检查
        </template>

        <el-descriptions
          :column="2"
          border
        >
          <el-descriptions-item label="文件存在">
            {{ verification.file_exists ? "是" : "否" }}
          </el-descriptions-item>

          <el-descriptions-item label="文件大小一致">
            {{ verification.size_match ? "是" : "否" }}
          </el-descriptions-item>

          <el-descriptions-item label="文件内容未变化">
            {{ verification.sha256_match ? "是" : "否" }}
          </el-descriptions-item>

          <el-descriptions-item label="成果内容可读取">
            {{
              verification.package_structure_valid === null
                ? "未执行"
                : verification.package_structure_valid
                  ? "是"
                  : "否"
            }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </template>
  </div>
</template>
