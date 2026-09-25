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
      "请选择由桌面端导出的成果文件",
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
        "成果文件已上传，基础检查通过，请继续进行业务核验",
      );
    } else {
      ElMessage.warning(
        `成果文件已保存，发现 ${row.inspection_error_count} 个需要处理的问题`,
      );
    }

    selectedFile.value = null;
    uploadFiles.value = [];
    await refresh();
  } catch (error: any) {
    ElMessage.error(
      uploadErrorMessage(error),
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
      <h1>成果接收与审核</h1>
      <p>
        上传桌面端导出的调查成果，系统自动核对任务范围，审核通过后统一进入成果库。
      </p>
    </div>
  </div>

  <el-alert
    class="linkage-alert"
    title="与桌面端联动：现场调查人员在桌面端完成记录并选择“成果提交”，将导出的成果文件交回中心，在本页上传、核验和审核。无需重复抄表或人工合并。"
    type="success"
    :closable="false"
    show-icon
  />

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
        :limit="1"
        accept=".ydresult"
        @change="fileChanged"
      >
        <el-button>选择成果文件</el-button>
      </el-upload>

      <el-button
        type="primary"
        :loading="uploading"
        :disabled="!selectedFile"
        @click="upload"
      >
        上传并核对文件
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
