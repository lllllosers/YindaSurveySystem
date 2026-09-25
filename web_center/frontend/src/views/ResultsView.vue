<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  ElMessage,
  type UploadFile,
} from "element-plus";

import {
  listResultSubmissions,
  resultDownloadUrl,
  uploadResultPackage,
  type ResultSubmission,
} from "../api/results";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const auth = useAuthStore();

const loading = ref(false);
const uploading = ref(false);
const rows = ref<ResultSubmission[]>([]);
const selectedFile = ref<File | null>(null);
const uploadFiles = ref<UploadFile[]>([]);
const statusFilter = ref("");

const canUpload = computed(
  () => auth.hasPermission("results.upload"),
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
  imported: "已入库",
};

const storageLabels: Record<string, string> = {
  unchecked: "未复检",
  ok: "完整",
  missing: "文件缺失",
  size_mismatch: "大小异常",
  hash_mismatch: "哈希异常",
  package_invalid: "包结构异常",
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
    return `${(value / 1024).toFixed(1)} KiB`;
  }
  if (value < 1024 ** 3) {
    return `${(value / 1024 ** 2).toFixed(1)} MiB`;
  }
  return `${(value / 1024 ** 3).toFixed(2)} GiB`;
}

function formatTime(value: string) {
  return new Date(value).toLocaleString(
    "zh-CN",
    { hour12: false },
  );
}

function apiErrorMessage(error: any): string {
  const detail = error?.response?.data?.detail;

  if (
    typeof detail === "string"
    && detail.trim()
  ) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (!item || typeof item !== "object") {
          return "";
        }

        const location = Array.isArray(item.loc)
          ? item.loc.join(".")
          : "";
        const message = (
          typeof item.msg === "string"
            ? item.msg
            : "请求参数无效"
        );

        return location
          ? `${location}: ${message}`
          : message;
      })
      .filter(Boolean);

    if (messages.length > 0) {
      return messages.join("；");
    }
  }

  return "成果包上传失败";
}

async function refresh() {
  loading.value = true;
  try {
    const data = await listResultSubmissions(
      statusFilter.value,
    );
    rows.value = data.items;
  } finally {
    loading.value = false;
  }
}

function fileChanged(uploadFile: UploadFile) {
  const raw = uploadFile.raw ?? null;

  if (
    raw
    && !raw.name.toLowerCase().endsWith(".ydresult")
  ) {
    ElMessage.error(
      "请选择 .ydresult 调查成果包",
    );
    selectedFile.value = null;
    uploadFiles.value = [];
    return;
  }

  selectedFile.value = raw;
}

function openDetail(row: ResultSubmission) {
  void router.push(
    `/results/${row.submission_uid}`,
  );
}

function download(row: ResultSubmission) {
  window.open(
    resultDownloadUrl(row.submission_uid),
    "_blank",
  );
}

async function upload() {
  if (!selectedFile.value) {
    return;
  }

  uploading.value = true;

  try {
    const row = await uploadResultPackage(
      selectedFile.value,
    );

    if (row.status === "inspected") {
      ElMessage.success(
        "成果包已上传，结构检查通过",
      );
    } else {
      ElMessage.warning(
        `成果包已保存，发现 ${row.inspection_error_count} 个结构问题`,
      );
    }

    selectedFile.value = null;
    uploadFiles.value = [];
    await refresh();
  } catch (error: any) {
    ElMessage.error(
      apiErrorMessage(error),
    );
  } finally {
    uploading.value = false;
  }
}

onMounted(refresh);
</script>

<template>
  <div class="module-header">
    <div>
      <h1>成果中心</h1>
      <p>
        接收桌面端 .ydresult 成果包，按下发任务冻结范围预检，
        完成审核后正式归集到中央成果库。
      </p>
    </div>
  </div>

  <el-card
    v-if="canUpload"
    shadow="never"
    class="business-card result-upload-card"
  >
    <template #header>
      <div class="card-header">
        <span>上传调查成果包</span>
        <el-tag
          type="info"
          effect="plain"
        >
          .ydresult
        </el-tag>
      </div>
    </template>

    <div class="result-upload-row">
      <el-upload
        v-model:file-list="uploadFiles"
        :auto-upload="false"
        :limit="1"
        accept=".ydresult"
        @change="fileChanged"
      >
        <el-button>选择成果包</el-button>
      </el-upload>

      <el-button
        type="primary"
        :loading="uploading"
        :disabled="!selectedFile"
        @click="upload"
      >
        上传并检查
      </el-button>
    </div>
  </el-card>

  <el-card
    shadow="never"
    class="business-card result-list-card"
  >
    <template #header>
      <div class="card-header">
        <span>成果提交记录</span>

        <div class="result-filter">
          <el-select
            v-model="statusFilter"
            clearable
            placeholder="全部状态"
            style="width: 180px"
            @change="refresh"
          >
            <el-option
              label="结构检查通过"
              value="inspected"
            />
            <el-option
              label="结构检查失败"
              value="invalid"
            />
            <el-option
              label="存在冲突"
              value="conflict"
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

          <el-button @click="refresh">
            刷新
          </el-button>
        </div>
      </div>
    </template>

    <el-table
      v-loading="loading"
      :data="rows"
    >
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
            {{ row.original_filename }}
          </div>
        </template>
      </el-table-column>

      <el-table-column
        label="提交状态"
        width="140"
      >
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">
            {{ statusLabels[row.status] || row.status }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column
        label="存储状态"
        width="125"
      >
        <template #default="{ row }">
          <el-tag :type="storageType(row.storage_status)">
            {{
              storageLabels[row.storage_status]
                || row.storage_status
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
            未发现结构问题
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

            <div
              v-for="issue in row.inspection_issues"
              :key="`${issue.code}-${issue.path}`"
              class="result-issue"
            >
              <b>{{ issue.code }}</b>：
              {{ issue.message }}
              <span v-if="issue.path">
                [{{ issue.path }}]
              </span>
            </div>
          </el-popover>
        </template>
      </el-table-column>

      <el-table-column
        label="操作"
        width="130"
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
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-if="!loading && rows.length === 0"
      description="尚无成果提交"
    />
  </el-card>
</template>
