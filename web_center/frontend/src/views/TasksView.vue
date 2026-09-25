<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { Download, Plus, Refresh, View } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";

import { getMasterDataSnapshot, type MasterDataSnapshot } from "../api/masterData";
import { listProjects, listSurveyBatches, type Project, type SurveyBatch } from "../api/projects";
import {
  cancelSurveyTask,
  createSurveyTask,
  downloadSurveyTask,
  getSurveyTask,
  listSurveyTasks,
  type SurveyTask,
  type SurveyTaskDetail,
  type TaskTargetType,
} from "../api/surveyTasks";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const loading = ref(false);
const submitting = ref(false);
const dialogVisible = ref(false);
const detailVisible = ref(false);
const formRef = ref<FormInstance>();
const projects = ref<Project[]>([]);
const batches = ref<SurveyBatch[]>([]);
const master = ref<MasterDataSnapshot | null>(null);
const tasks = ref<SurveyTask[]>([]);
const detail = ref<SurveyTaskDetail | null>(null);

const form = reactive({
  project_uid: "",
  survey_batch_uid: "",
  task_name: "",
  notes: "",
  target_unit_type: "department" as TaskTargetType,
  target_master_key: "",
  selected_management_scope_uids: [] as string[],
});

const rules: FormRules = {
  project_uid: [{ required: true, message: "请选择项目", trigger: "change" }],
  survey_batch_uid: [{ required: true, message: "请选择进行中批次", trigger: "change" }],
  task_name: [{ required: true, message: "请输入任务名称", trigger: "blur" }],
  target_master_key: [{ required: true, message: "请选择任务目标单位", trigger: "change" }],
  selected_management_scope_uids: [{ type: "array", required: true, min: 1, message: "至少选择一个分管范围", trigger: "change" }],
};

const canWrite = computed(() => auth.hasPermission("tasks.write"));
const canDownload = computed(() => auth.hasPermission("tasks.download"));
const activeProjects = computed(() => projects.value.filter((item) => item.status === "active"));
const activeBatches = computed(() => batches.value.filter((item) => item.status === "active"));
const targetOptions = computed(() => {
  if (!master.value) return [];
  return form.target_unit_type === "department" ? master.value.departments : master.value.offices;
});
const eligibleScopes = computed(() => {
  if (!master.value || !form.target_master_key) return [];
  if (form.target_unit_type === "water_office") {
    return master.value.management_scopes.filter(
      (item) => item.organization_master_key === form.target_master_key,
    );
  }
  const officeKeys = new Set(
    master.value.offices
      .filter((item) => item.parent_master_key === form.target_master_key)
      .map((item) => item.master_key),
  );
  return master.value.management_scopes.filter((item) => officeKeys.has(item.organization_master_key));
});

const statusLabels: Record<string, string> = {
  issued: "待下载",
  downloaded: "已下载",
  result_received: "已有成果返回",
  closed: "已关闭",
  cancelled: "已取消",
};
const statusTypes: Record<string, "success" | "warning" | "info" | "danger"> = {
  issued: "warning",
  downloaded: "success",
  result_received: "success",
  closed: "info",
  cancelled: "danger",
};

function rangeText(item: MasterDataSnapshot["management_scopes"][number] | SurveyTaskDetail["frozen_scopes"][number]) {
  if (item.range_mode === "whole") return "全段";
  if (item.range_mode === "segment_unknown") return "分段（桩号待定）";
  return `${item.start_stake_text ?? "-"} — ${item.end_stake_text ?? "-"}`;
}

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—";
}

function formatSize(value: number) {
  return value < 1024 * 1024 ? `${(value / 1024).toFixed(1)} KB` : `${(value / 1024 / 1024).toFixed(1)} MB`;
}

async function loadAll() {
  loading.value = true;
  try {
    const [projectData, masterData, taskData] = await Promise.all([
      listProjects(),
      getMasterDataSnapshot(),
      listSurveyTasks(),
    ]);
    projects.value = projectData;
    master.value = masterData;
    tasks.value = taskData.items;
  } catch {
    ElMessage.error("任务中心数据加载失败");
  } finally {
    loading.value = false;
  }
}

async function onProjectChange() {
  form.survey_batch_uid = "";
  batches.value = form.project_uid ? await listSurveyBatches(form.project_uid) : [];
}

watch(
  () => [form.target_unit_type, form.target_master_key],
  () => {
    form.selected_management_scope_uids = eligibleScopes.value.map((item) => item.stable_uid);
  },
);

function openCreate() {
  Object.assign(form, {
    project_uid: "",
    survey_batch_uid: "",
    task_name: "",
    notes: "",
    target_unit_type: "department",
    target_master_key: "",
    selected_management_scope_uids: [],
  });
  batches.value = [];
  dialogVisible.value = true;
}

async function submit() {
  if (!(await formRef.value?.validate())) return;
  submitting.value = true;
  try {
    const created = await createSurveyTask({ ...form, notes: form.notes || null });
    dialogVisible.value = false;
    ElMessage.success("调查任务已生成并下载，请在桌面端的“任务接收”中导入");
    await loadAll();
    await doDownload(created);
  } catch {
    ElMessage.error("任务生成失败，请检查项目、批次和调查范围后重试");
  } finally {
    submitting.value = false;
  }
}

async function doDownload(task: SurveyTask) {
  try {
    await downloadSurveyTask(task);
    ElMessage.success("任务文件已下载，可在桌面端“任务接收”中导入");
    await loadAll();
  } catch {
    ElMessage.error("任务文件下载失败，请稍后重试");
  }
}

async function showDetail(task: SurveyTask) {
  try {
    detail.value = await getSurveyTask(task.task_uid);
    detailVisible.value = true;
  } catch {
    ElMessage.error("任务详情读取失败，请稍后重试");
  }
}

async function cancel(task: SurveyTask) {
  try {
    await ElMessageBox.confirm(`确认取消任务“${task.task_name}”吗？已经交给基层的任务文件仍需另行通知停止使用。`, "取消任务", { type: "warning" });
    await cancelSurveyTask(task.task_uid);
    ElMessage.success("任务已取消");
    await loadAll();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error("任务取消失败，请稍后重试");
  }
}

onMounted(loadAll);
</script>

<template>
  <div class="module-header">
    <div>
      <div class="eyebrow">调查工作安排</div>
      <h1>调查任务中心</h1>
      <p>在中心确定调查单位和范围，下载任务文件后交给基层人员在桌面端开展调查。</p>
    </div>
    <div class="header-actions">
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      <el-button v-if="canWrite" type="primary" :icon="Plus" @click="openCreate">新建并下发任务</el-button>
    </div>
  </div>

  <el-alert
    class="linkage-alert"
    title="与桌面端联动：中心下发任务文件 → 基层桌面端“任务接收”导入 → 完成现场调查后由桌面端导出成果文件 → 回到成果中心上传。"
    type="success"
    :closable="false"
    show-icon
  />

  <div class="task-stat-row">
    <div><span>任务总数</span><strong>{{ tasks.length }}</strong></div>
    <div><span>待下载</span><strong>{{ tasks.filter((item) => item.status === 'issued').length }}</strong></div>
    <div><span>已下载</span><strong>{{ tasks.filter((item) => item.status === 'downloaded').length }}</strong></div>
    <div><span>已有成果</span><strong>{{ tasks.filter((item) => item.status === 'result_received').length }}</strong></div>
  </div>

  <el-card shadow="never" class="business-card task-list-card" v-loading="loading">
    <el-table :data="tasks" stripe height="570" empty-text="尚未下发调查任务">
      <el-table-column prop="task_name" label="任务" min-width="210">
        <template #default="scope">
          <div class="task-name">{{ scope.row.task_name }}</div>
          <div class="result-secondary">{{ scope.row.project_name }} · {{ scope.row.batch_name }}</div>
        </template>
      </el-table-column>
      <el-table-column label="目标单位" min-width="180">
        <template #default="scope">
          <div>{{ scope.row.organization_name }}</div>
          <div class="result-secondary">{{ scope.row.target_unit_type === 'department' ? '交由管理处分派到所属水管所' : '直接交由水管所调查' }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="selected_scope_count" label="分管范围" width="100" align="center" />
      <el-table-column prop="form_count" label="调查表" width="85" align="center" />
      <el-table-column label="状态" width="120">
        <template #default="scope"><el-tag :type="statusTypes[scope.row.status]" effect="light">{{ statusLabels[scope.row.status] || "状态待确认" }}</el-tag></template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="scope">{{ formatTime(scope.row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="scope">
          <el-button link :icon="View" @click="showDetail(scope.row)">详情</el-button>
          <el-button v-if="canDownload && scope.row.status !== 'cancelled'" link type="primary" :icon="Download" @click="doDownload(scope.row)">下载</el-button>
          <el-button v-if="canWrite && ['issued', 'downloaded'].includes(scope.row.status)" link type="danger" @click="cancel(scope.row)">取消</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="dialogVisible" title="新建调查任务" width="760px" destroy-on-close>
    <el-alert title="任务生成后，本次调查的单位、渠道和范围将固定保存，后续基础资料调整不会影响已经开展的调查。" type="info" :closable="false" show-icon />
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="task-create-form">
      <div class="two-column-form">
        <el-form-item label="项目" prop="project_uid">
          <el-select v-model="form.project_uid" placeholder="选择启用项目" filterable @change="onProjectChange">
            <el-option v-for="item in activeProjects" :key="item.project_uid" :label="item.name" :value="item.project_uid" />
          </el-select>
        </el-form-item>
        <el-form-item label="进行中调查批次" prop="survey_batch_uid">
          <el-select v-model="form.survey_batch_uid" placeholder="先选择项目" filterable>
            <el-option v-for="item in activeBatches" :key="item.survey_batch_uid" :label="`${item.batch_name}（${item.batch_code}）`" :value="item.survey_batch_uid" />
          </el-select>
        </el-form-item>
        <el-form-item label="任务名称" prop="task_name">
          <el-input v-model="form.task_name" placeholder="例如：2026年度总干渠处现状调查" maxlength="240" />
        </el-form-item>
        <el-form-item label="下发方式" prop="target_unit_type">
          <el-segmented v-model="form.target_unit_type" :options="[{ label: '整个管理处', value: 'department' }, { label: '指定水管所', value: 'water_office' }]" />
        </el-form-item>
      </div>
      <el-form-item label="任务目标单位" prop="target_master_key">
        <el-select v-model="form.target_master_key" placeholder="请选择" filterable>
          <el-option v-for="item in targetOptions" :key="item.master_key" :label="item.name" :value="item.master_key" />
        </el-select>
      </el-form-item>
      <el-form-item label="本次调查范围" prop="selected_management_scope_uids">
        <div class="scope-picker">
          <div class="scope-picker-toolbar">
            <span>已选择 {{ form.selected_management_scope_uids.length }} / {{ eligibleScopes.length }} 项</span>
            <el-button link type="primary" @click="form.selected_management_scope_uids = eligibleScopes.map((item) => item.stable_uid)">全选</el-button>
            <el-button link @click="form.selected_management_scope_uids = []">清空</el-button>
          </div>
          <el-checkbox-group v-model="form.selected_management_scope_uids">
            <div v-for="item in eligibleScopes" :key="item.stable_uid" class="scope-option">
              <el-checkbox :value="item.stable_uid">
                <strong>{{ item.canal_name }}</strong>
                <span>{{ item.organization_name }} · {{ rangeText(item) }}</span>
              </el-checkbox>
            </div>
          </el-checkbox-group>
          <el-empty v-if="form.target_master_key && !eligibleScopes.length" description="该单位暂无已确认的正式分管范围" :image-size="60" />
        </div>
      </el-form-item>
      <el-form-item label="任务说明（选填）">
        <el-input v-model="form.notes" type="textarea" :rows="3" maxlength="2000" show-word-limit />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">生成任务并下载</el-button>
    </template>
  </el-dialog>

  <el-drawer v-model="detailVisible" title="调查任务详情" size="620px">
    <template v-if="detail">
      <div class="task-detail-hero">
        <el-tag :type="statusTypes[detail.status]">{{ statusLabels[detail.status] || "状态待确认" }}</el-tag>
        <h2>{{ detail.task_name }}</h2>
        <p>{{ detail.project_name }} · {{ detail.batch_name }}</p>
      </div>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="目标单位">{{ detail.organization_name }}</el-descriptions-item>
        <el-descriptions-item label="下发方式">{{ detail.target_unit_type === 'department' ? '管理处统一接收并分派' : '水管所直接接收' }}</el-descriptions-item>
        <el-descriptions-item label="分管范围">{{ detail.selected_scope_count }} 项</el-descriptions-item>
        <el-descriptions-item label="调查表">{{ detail.form_count }} 张</el-descriptions-item>
        <el-descriptions-item label="下载次数">{{ detail.download_count }}</el-descriptions-item>
        <el-descriptions-item label="文件大小">{{ formatSize(detail.file_size) }}</el-descriptions-item>
        <el-descriptions-item label="调查依据" :span="2">任务下发时的正式组织、渠道和分管范围</el-descriptions-item>
        <el-descriptions-item label="创建人员">{{ detail.created_by_username }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatTime(detail.created_at) }}</el-descriptions-item>
      </el-descriptions>
      <h3 class="drawer-section-title">本次确定的调查范围</h3>
      <div v-for="item in detail.frozen_scopes" :key="item.management_scope_uid" class="frozen-scope-row">
        <div><strong>{{ item.canal_name }}</strong><span>{{ item.organization_name }}</span></div>
        <el-tag effect="plain">{{ rangeText(item) }}</el-tag>
      </div>
    </template>
  </el-drawer>
</template>
