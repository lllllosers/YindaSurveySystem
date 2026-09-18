<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
} from "element-plus";
import {
  createProject,
  createSurveyBatch,
  deleteProject,
  deleteSurveyBatch,
  listProjects,
  listSurveyBatches,
  updateProject,
  updateSurveyBatch,
  type Project,
  type ProjectPayload,
  type SurveyBatch,
  type SurveyBatchPayload,
} from "../api/projects";

const loadingProjects = ref(false);
const loadingBatches = ref(false);
const projects = ref<Project[]>([]);
const batches = ref<SurveyBatch[]>([]);
const selectedProject = ref<Project | null>(null);

const projectDialogVisible = ref(false);
const batchDialogVisible = ref(false);
const editingProjectUid = ref<string | null>(null);
const editingBatchUid = ref<string | null>(null);

const projectFormRef = ref<FormInstance>();
const batchFormRef = ref<FormInstance>();

const projectForm = reactive<ProjectPayload>({
  name: "",
  short_name: "",
  status: "active",
});

const batchForm = reactive<SurveyBatchPayload>({
  batch_name: "",
  batch_code: "",
  start_date: null,
  end_date: null,
  status: "planned",
});

const projectRules: FormRules<ProjectPayload> = {
  name: [{ required: true, message: "请输入项目名称", trigger: "blur" }],
};

const batchRules: FormRules<SurveyBatchPayload> = {
  batch_name: [
    { required: true, message: "请输入调查批次名称", trigger: "blur" },
  ],
  batch_code: [
    { required: true, message: "请输入批次编码", trigger: "blur" },
  ],
};

const selectedProjectTitle = computed(() =>
  selectedProject.value
    ? `${selectedProject.value.name} · 调查批次`
    : "调查批次",
);

function projectStatusLabel(status: Project["status"]) {
  return status === "active" ? "启用" : "归档";
}

function batchStatusLabel(status: SurveyBatch["status"]) {
  return {
    planned: "计划中",
    active: "进行中",
    closed: "已结束",
  }[status];
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

async function refreshProjects(preferredUid?: string) {
  loadingProjects.value = true;
  try {
    projects.value = await listProjects();

    const uid = preferredUid ?? selectedProject.value?.project_uid;
    selectedProject.value =
      projects.value.find((item) => item.project_uid === uid) ??
      projects.value[0] ??
      null;

    await refreshBatches();
  } catch (error) {
    console.error(error);
    ElMessage.error("项目数据加载失败");
  } finally {
    loadingProjects.value = false;
  }
}

async function refreshBatches() {
  batches.value = [];
  if (!selectedProject.value) return;

  loadingBatches.value = true;
  try {
    batches.value = await listSurveyBatches(
      selectedProject.value.project_uid,
    );
  } catch (error) {
    console.error(error);
    ElMessage.error("调查批次加载失败");
  } finally {
    loadingBatches.value = false;
  }
}

async function selectProject(project: Project) {
  selectedProject.value = project;
  await refreshBatches();
}

function openCreateProject() {
  editingProjectUid.value = null;
  projectForm.name = "";
  projectForm.short_name = "";
  projectForm.status = "active";
  projectDialogVisible.value = true;
}

function openEditProject(project: Project) {
  editingProjectUid.value = project.project_uid;
  projectForm.name = project.name;
  projectForm.short_name = project.short_name ?? "";
  projectForm.status = project.status;
  projectDialogVisible.value = true;
}

async function saveProject() {
  if (!(await projectFormRef.value?.validate())) return;

  try {
    const payload: ProjectPayload = {
      name: projectForm.name.trim(),
      short_name: projectForm.short_name?.trim() || null,
      status: projectForm.status,
    };

    const editing = editingProjectUid.value !== null;
    const saved = editing
      ? await updateProject(editingProjectUid.value!, payload)
      : await createProject(payload);

    projectDialogVisible.value = false;
    ElMessage.success(editing ? "项目已更新" : "项目已创建");
    await refreshProjects(saved.project_uid);
  } catch (error) {
    console.error(error);
    ElMessage.error("项目保存失败");
  }
}

async function removeProject(project: Project) {
  try {
    await ElMessageBox.confirm(
      `确认删除项目“${project.name}”？只有不存在调查批次时才允许删除。`,
      "删除项目",
      {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
    await deleteProject(project.project_uid);
    ElMessage.success("项目已删除");
    await refreshProjects();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    console.error(error);
    ElMessage.error("删除失败；请确认项目下不存在调查批次");
  }
}

function openCreateBatch() {
  if (!selectedProject.value) {
    ElMessage.warning("请先创建并选择项目");
    return;
  }

  editingBatchUid.value = null;
  batchForm.batch_name = "";
  batchForm.batch_code = "";
  batchForm.start_date = null;
  batchForm.end_date = null;
  batchForm.status = "planned";
  batchDialogVisible.value = true;
}

function openEditBatch(batch: SurveyBatch) {
  editingBatchUid.value = batch.survey_batch_uid;
  batchForm.batch_name = batch.batch_name;
  batchForm.batch_code = batch.batch_code;
  batchForm.start_date = batch.start_date;
  batchForm.end_date = batch.end_date;
  batchForm.status = batch.status;
  batchDialogVisible.value = true;
}

async function saveBatch() {
  if (!(await batchFormRef.value?.validate())) return;
  if (!selectedProject.value) return;

  try {
    const payload: SurveyBatchPayload = {
      batch_name: batchForm.batch_name.trim(),
      batch_code: batchForm.batch_code.trim(),
      start_date: batchForm.start_date || null,
      end_date: batchForm.end_date || null,
      status: batchForm.status,
    };

    const editing = editingBatchUid.value !== null;
    if (editing) {
      await updateSurveyBatch(editingBatchUid.value!, payload);
    } else {
      await createSurveyBatch(
        selectedProject.value.project_uid,
        payload,
      );
    }

    batchDialogVisible.value = false;
    ElMessage.success(editing ? "批次已更新" : "批次已创建");
    await refreshBatches();
  } catch (error) {
    console.error(error);
    ElMessage.error("批次保存失败；请检查日期或批次编码");
  }
}

async function removeBatch(batch: SurveyBatch) {
  try {
    await ElMessageBox.confirm(
      `确认删除调查批次“${batch.batch_name}”？`,
      "删除调查批次",
      {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
    await deleteSurveyBatch(batch.survey_batch_uid);
    ElMessage.success("调查批次已删除");
    await refreshBatches();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    console.error(error);
    ElMessage.error("调查批次删除失败");
  }
}

onMounted(() => refreshProjects());
</script>

<template>
  <div class="module-header">
    <div>
      <h1>项目与调查批次</h1>
      <p>
        Web 中心主数据入口。稳定 UID 用于后续 .ydtask / .ydresult 跨数据库交换。
      </p>
    </div>
    <el-button type="primary" @click="openCreateProject">
      新建项目
    </el-button>
  </div>

  <el-card shadow="never" class="business-card">
    <template #header>
      <div class="card-header">
        <span>项目</span>
        <el-tag type="info">{{ projects.length }} 个</el-tag>
      </div>
    </template>

    <el-table
      v-loading="loadingProjects"
      :data="projects"
      highlight-current-row
      @row-click="selectProject"
    >
      <el-table-column prop="name" label="项目名称" min-width="220" />
      <el-table-column prop="short_name" label="简称" width="150">
        <template #default="{ row }">
          {{ row.short_name || "—" }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag
            :type="row.status === 'active' ? 'success' : 'info'"
            effect="light"
          >
            {{ projectStatusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="稳定 UID" min-width="285">
        <template #default="{ row }">
          <span class="mono">{{ row.project_uid }}</span>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="185">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click.stop="openEditProject(row)">
            编辑
          </el-button>
          <el-button link type="danger" @click.stop="removeProject(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-if="!loadingProjects && projects.length === 0"
      description="尚未创建项目"
    />
  </el-card>

  <el-card shadow="never" class="business-card batches-card">
    <template #header>
      <div class="card-header">
        <div>
          <span>{{ selectedProjectTitle }}</span>
          <span v-if="selectedProject" class="selected-hint">
            当前项目：{{ selectedProject.name }}
          </span>
        </div>
        <el-button
          type="primary"
          plain
          :disabled="!selectedProject"
          @click="openCreateBatch"
        >
          新建调查批次
        </el-button>
      </div>
    </template>

    <el-table
      v-if="selectedProject"
      v-loading="loadingBatches"
      :data="batches"
    >
      <el-table-column prop="batch_name" label="批次名称" min-width="210" />
      <el-table-column prop="batch_code" label="批次编码" width="150" />
      <el-table-column label="调查时间" width="220">
        <template #default="{ row }">
          {{ row.start_date || "—" }} 至 {{ row.end_date || "—" }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag
            :type="
              row.status === 'active'
                ? 'success'
                : row.status === 'closed'
                  ? 'info'
                  : 'warning'
            "
            effect="light"
          >
            {{ batchStatusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="稳定 UID" min-width="285">
        <template #default="{ row }">
          <span class="mono">{{ row.survey_batch_uid }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEditBatch(row)">
            编辑
          </el-button>
          <el-button link type="danger" @click="removeBatch(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-if="!selectedProject"
      description="请先创建并选择一个项目"
    />
    <el-empty
      v-else-if="!loadingBatches && batches.length === 0"
      description="该项目尚未创建调查批次"
    />
  </el-card>

  <el-dialog
    v-model="projectDialogVisible"
    :title="editingProjectUid ? '编辑项目' : '新建项目'"
    width="520px"
    destroy-on-close
  >
    <el-form
      ref="projectFormRef"
      :model="projectForm"
      :rules="projectRules"
      label-width="90px"
    >
      <el-form-item label="项目名称" prop="name">
        <el-input v-model="projectForm.name" maxlength="200" />
      </el-form-item>
      <el-form-item label="项目简称">
        <el-input v-model="projectForm.short_name" maxlength="100" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="projectForm.status" style="width: 100%">
          <el-option label="启用" value="active" />
          <el-option label="归档" value="archived" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="projectDialogVisible = false">取消</el-button>
      <el-button type="primary" @click="saveProject">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="batchDialogVisible"
    :title="editingBatchUid ? '编辑调查批次' : '新建调查批次'"
    width="560px"
    destroy-on-close
  >
    <el-form
      ref="batchFormRef"
      :model="batchForm"
      :rules="batchRules"
      label-width="100px"
    >
      <el-form-item label="批次名称" prop="batch_name">
        <el-input v-model="batchForm.batch_name" maxlength="200" />
      </el-form-item>
      <el-form-item label="批次编码" prop="batch_code">
        <el-input
          v-model="batchForm.batch_code"
          maxlength="50"
          placeholder="例如：2026-01"
        />
      </el-form-item>
      <el-form-item label="调查日期">
        <el-date-picker
          v-model="batchForm.start_date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="开始日期"
          style="width: 47%"
        />
        <span class="date-separator">至</span>
        <el-date-picker
          v-model="batchForm.end_date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="结束日期"
          style="width: 47%"
        />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="batchForm.status" style="width: 100%">
          <el-option label="计划中" value="planned" />
          <el-option label="进行中" value="active" />
          <el-option label="已结束" value="closed" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="batchDialogVisible = false">取消</el-button>
      <el-button type="primary" @click="saveBatch">保存</el-button>
    </template>
  </el-dialog>
</template>
