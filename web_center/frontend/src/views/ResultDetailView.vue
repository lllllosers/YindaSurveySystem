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
import { ElMessage } from "element-plus";

import {
  getResultSubmission,
  resultDownloadUrl,
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
const row = ref<ResultSubmission | null>(null);
const verification = ref<ResultFileVerification | null>(null);

const submissionUid = computed(
  () => String(route.params.submissionUid ?? ""),
);

const canVerify = computed(
  () => auth.hasPermission("results.verify"),
);

const statusLabels: Record<string, string> = {
  uploaded: "已上传",
  inspected: "结构检查通过",
  invalid: "结构检查失败",
  preflight_passed: "业务预检通过",
  conflict: "存在冲突",
  reviewing: "审核中",
  accepted: "已接收",
  rejected: "已退回",
};

const storageLabels: Record<string, string> = {
  unchecked: "未复检",
  ok: "完整",
  missing: "文件缺失",
  size_mismatch: "大小不一致",
  hash_mismatch: "SHA-256 不一致",
  package_invalid: "包结构异常",
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
    return `${(value / 1024).toFixed(1)} KiB`;
  }
  if (value < 1024 ** 3) {
    return `${(value / 1024 ** 2).toFixed(1)} MiB`;
  }
  return `${(value / 1024 ** 3).toFixed(2)} GiB`;
}

function formatTime(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString(
    "zh-CN",
    { hour12: false },
  );
}

async function refresh() {
  loading.value = true;

  try {
    row.value = await getResultSubmission(
      submissionUid.value,
    );
  } catch (error: any) {
    ElMessage.error(
      error?.response?.data?.detail
        ?? "成果提交读取失败",
    );
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
        "服务器文件完整性复检通过",
      );
    } else {
      ElMessage.warning(
        "复检发现服务器文件完整性问题",
      );
    }
  } catch (error: any) {
    ElMessage.error(
      error?.response?.data?.detail
        ?? "完整性复检失败",
    );
  } finally {
    verifying.value = false;
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
      <h1>成果提交详情</h1>
      <p>
        查看成果包标识、来源、结构检查结果和服务器文件完整性状态。
      </p>
    </div>

    <div class="detail-actions">
      <el-button @click="back">
        返回成果中心
      </el-button>

      <el-button @click="download">
        下载原包
      </el-button>

      <el-button
        v-if="canVerify"
        type="primary"
        :loading="verifying"
        @click="verifyFile"
      >
        重新校验文件
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
                {{ statusLabels[row.status] || row.status }}
              </el-tag>

              <el-tag
                :type="storageTagType(row.storage_status)"
              >
                {{
                  storageLabels[row.storage_status]
                    || row.storage_status
                }}
              </el-tag>
            </div>
          </div>
        </template>

        <el-descriptions
          :column="2"
          border
        >
          <el-descriptions-item label="提交 UID">
            <span class="mono">
              {{ row.submission_uid }}
            </span>
          </el-descriptions-item>

          <el-descriptions-item label="Package UID">
            <span class="mono">
              {{ row.package_uid || "—" }}
            </span>
          </el-descriptions-item>

          <el-descriptions-item label="Result UID">
            <span class="mono">
              {{ row.result_uid || "—" }}
            </span>
          </el-descriptions-item>

          <el-descriptions-item label="项目 UID">
            <span class="mono">
              {{ row.project_uid || "—" }}
            </span>
          </el-descriptions-item>

          <el-descriptions-item label="调查批次 UID">
            <span class="mono">
              {{ row.survey_batch_uid || "—" }}
            </span>
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

          <el-descriptions-item
            label="SHA-256"
            :span="2"
          >
            <span class="mono detail-hash">
              {{ row.file_sha256 }}
            </span>
          </el-descriptions-item>

          <el-descriptions-item label="桌面端版本">
            {{
              row.desktop_app_version_label
                || row.desktop_app_version
                || "—"
            }}
          </el-descriptions-item>

          <el-descriptions-item label="包协议版本">
            {{ row.package_format_version || "—" }}
          </el-descriptions-item>

          <el-descriptions-item label="调查记录数">
            {{ row.counts.survey_records ?? "—" }}
          </el-descriptions-item>

          <el-descriptions-item label="影像数">
            {{ row.counts.survey_media ?? "—" }}
          </el-descriptions-item>

          <el-descriptions-item label="最近文件复检">
            {{ formatTime(row.storage_checked_at) }}
          </el-descriptions-item>

          <el-descriptions-item label="存储状态">
            {{
              storageLabels[row.storage_status]
                || row.storage_status
            }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card
        shadow="never"
        class="business-card detail-card"
      >
        <template #header>
          来源任务
        </template>

        <el-empty
          v-if="row.source_task_uids.length === 0"
          description="成果包未声明来源任务"
        />

        <div
          v-for="uid in row.source_task_uids"
          :key="uid"
          class="detail-uid-row mono"
        >
          {{ uid }}
        </div>
      </el-card>

      <el-card
        shadow="never"
        class="business-card detail-card"
      >
        <template #header>
          上传时结构检查
        </template>

        <el-result
          v-if="row.inspection_error_count === 0"
          icon="success"
          title="结构检查通过"
          sub-title="上传时未发现成果包结构、清单或哈希问题。"
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
            <b>{{ issue.code }}</b>：
            {{ issue.message }}
            <span v-if="issue.path">
              [{{ issue.path }}]
            </span>
          </div>
        </div>
      </el-card>

      <el-card
        v-if="verification"
        shadow="never"
        class="business-card detail-card"
      >
        <template #header>
          本次文件完整性复检
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

          <el-descriptions-item label="SHA-256 一致">
            {{ verification.sha256_match ? "是" : "否" }}
          </el-descriptions-item>

          <el-descriptions-item label="包结构有效">
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
