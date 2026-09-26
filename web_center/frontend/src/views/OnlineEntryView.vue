<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Check, Edit, Plus, Refresh, UploadFilled, View } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  createOnlineEntry,
  deleteOnlineMedia,
  getOnlineFormDefinitions,
  listOnlineEntries,
  onlineMediaUrl,
  reviewOnlineEntry,
  submitOnlineEntry,
  updateOnlineEntry,
  uploadOnlineMedia,
  type FormField,
  type OnlineEntry,
  type OnlineFormDefinition,
} from "../api/onlineEntries";
import { getSurveyTask, listSurveyTasks, type FrozenScope, type SurveyTask, type SurveyTaskDetail } from "../api/surveyTasks";
import { useAuthStore } from "../stores/auth";

interface EntryEvaluation {
  item_code: string;
  category: string;
  item_name: string;
  grade: string;
  description: string;
  remark: string;
}

const auth = useAuthStore();
const loading = ref(false);
const saving = ref(false);
const drawerVisible = ref(false);
const detailVisible = ref(false);
const entries = ref<OnlineEntry[]>([]);
const tasks = ref<SurveyTask[]>([]);
const taskDetail = ref<SurveyTaskDetail | null>(null);
const definitions = ref<OnlineFormDefinition[]>([]);
const selectedEntry = ref<OnlineEntry | null>(null);
const editingUid = ref("");
const mediaInput = ref<HTMLInputElement>();
const uploadingMedia = ref(false);
const selector = reactive({ task_uid: "", management_scope_uid: "", form_code: "" });
const formData = ref<Record<string, unknown>>({});
const evaluations = ref<EntryEvaluation[]>([]);
const conclusion = reactive({
  survey_date: "",
  overall_grade: "",
  survey_comment: "",
  surveyor_signatures: "",
  water_office_manager_signature: "",
  engineering_section_chief_signature: "",
  department_head_signature: "",
});

const canWrite = computed(() => auth.hasPermission("online_entries.write"));
const canReview = computed(() => auth.hasPermission("online_entries.review"));
const activeTasks = computed(() => tasks.value.filter((item) => !["cancelled", "closed"].includes(item.status)));
const selectedDefinition = computed(() => definitions.value.find((item) => item.form_code === selector.form_code) ?? null);
const fieldMap = computed(() => new Map(selectedDefinition.value?.fields.map((item) => [item.key, item]) ?? []));
const scopes = computed(() => taskDetail.value?.frozen_scopes ?? []);
const editable = computed(() => !selectedEntry.value || ["draft", "rejected"].includes(selectedEntry.value.status));

const statusLabels: Record<string, string> = {
  draft: "草稿",
  submitted: "待审核",
  accepted: "审核通过",
  rejected: "已退回",
  imported: "已入正式库",
};
const statusTypes: Record<string, "info" | "warning" | "success" | "danger"> = {
  draft: "info",
  submitted: "warning",
  accepted: "success",
  rejected: "danger",
  imported: "success",
};

function errorMessage(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return typeof detail === "string" && detail ? detail : fallback;
}

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—";
}

function formatSize(value: number) {
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function rangeText(scope: FrozenScope) {
  if (scope.range_mode === "whole") return "全段";
  if (scope.range_mode === "segment_unknown") return "分段（桩号待定）";
  return `${scope.start_stake_text ?? "-"} — ${scope.end_stake_text ?? "-"}`;
}

function fieldOf(key: string): FormField | undefined {
  return fieldMap.value.get(key);
}

function selectedStandard(item: EntryEvaluation): string {
  return selectedDefinition.value?.evaluation_items
    .find((candidate) => candidate.item_code === item.item_code)
    ?.standards[item.grade] ?? "";
}

async function loadAll() {
  loading.value = true;
  try {
    const [entryPage, taskPage, formDefinitions] = await Promise.all([
      listOnlineEntries(),
      listSurveyTasks(),
      getOnlineFormDefinitions(),
    ]);
    entries.value = entryPage.items;
    tasks.value = taskPage.items;
    definitions.value = formDefinitions;
  } catch (error) {
    ElMessage.error(errorMessage(error, "在线调查记录加载失败，请稍后重试"));
  } finally {
    loading.value = false;
  }
}

function resetContent() {
  formData.value = {};
  evaluations.value = [];
  Object.assign(conclusion, {
    survey_date: new Date().toISOString().slice(0, 10),
    overall_grade: "",
    survey_comment: "",
    surveyor_signatures: "",
    water_office_manager_signature: "",
    engineering_section_chief_signature: "",
    department_head_signature: "",
  });
}

function initializeEvaluations(definition: OnlineFormDefinition) {
  evaluations.value = definition.evaluation_items.map((item) => ({
    item_code: item.item_code,
    category: item.category,
    item_name: item.item_name,
    grade: "",
    description: "",
    remark: "",
  }));
}

async function openCreate() {
  editingUid.value = "";
  selectedEntry.value = null;
  Object.assign(selector, { task_uid: "", management_scope_uid: "", form_code: "" });
  taskDetail.value = null;
  resetContent();
  drawerVisible.value = true;
}

async function onTaskChange() {
  selector.management_scope_uid = "";
  taskDetail.value = selector.task_uid ? await getSurveyTask(selector.task_uid) : null;
}

function onFormChange() {
  resetContent();
  if (selectedDefinition.value) initializeEvaluations(selectedDefinition.value);
}

async function openEdit(row: OnlineEntry) {
  selectedEntry.value = row;
  editingUid.value = row.entry_uid;
  Object.assign(selector, {
    task_uid: row.task_uid,
    management_scope_uid: row.management_scope_uid,
    form_code: row.form_code,
  });
  taskDetail.value = await getSurveyTask(row.task_uid);
  formData.value = { ...row.form_data };
  const definition = definitions.value.find((item) => item.form_code === row.form_code);
  const saved = new Map(row.evaluations.map((item) => [String(item.item_code), item]));
  evaluations.value = (definition?.evaluation_items ?? []).map((item) => ({
    item_code: item.item_code,
    category: item.category,
    item_name: item.item_name,
    grade: String(saved.get(item.item_code)?.grade ?? ""),
    description: String(saved.get(item.item_code)?.description ?? ""),
    remark: String(saved.get(item.item_code)?.remark ?? ""),
  }));
  Object.assign(conclusion, {
    survey_date: String(row.conclusion.survey_date ?? ""),
    overall_grade: String(row.conclusion.overall_grade ?? ""),
    survey_comment: String(row.conclusion.survey_comment ?? ""),
    surveyor_signatures: String(row.conclusion.surveyor_signatures ?? ""),
    water_office_manager_signature: String(row.conclusion.water_office_manager_signature ?? ""),
    engineering_section_chief_signature: String(row.conclusion.engineering_section_chief_signature ?? ""),
    department_head_signature: String(row.conclusion.department_head_signature ?? ""),
  });
  drawerVisible.value = true;
}

function contentPayload() {
  return {
    form_data: { ...formData.value },
    evaluations: evaluations.value.map((item) => ({ ...item })),
    conclusion: { ...conclusion },
  };
}

async function saveDraft(showMessage = true): Promise<OnlineEntry | null> {
  if (!selector.task_uid || !selector.management_scope_uid || !selector.form_code) {
    ElMessage.warning("请先选择调查任务、调查范围和调查表");
    return null;
  }
  saving.value = true;
  try {
    const row = editingUid.value
      ? await updateOnlineEntry(editingUid.value, contentPayload())
      : await createOnlineEntry({
          task_uid: selector.task_uid,
          management_scope_uid: selector.management_scope_uid,
          form_code: selector.form_code,
          ...contentPayload(),
        });
    editingUid.value = row.entry_uid;
    selectedEntry.value = row;
    if (showMessage) ElMessage.success("草稿已保存");
    await loadAll();
    return row;
  } catch (error) {
    ElMessage.error(errorMessage(error, "草稿保存失败，请稍后重试"));
    return null;
  } finally {
    saving.value = false;
  }
}

async function chooseMedia() {
  if (!editingUid.value) {
    const row = await saveDraft(false);
    if (!row) return;
    ElMessage.success("草稿已保存，现在可以添加现场影像");
  }
  mediaInput.value?.click();
}

async function addSelectedMedia(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  input.value = "";
  if (!files.length || !editingUid.value) return;
  uploadingMedia.value = true;
  let success = 0;
  for (const file of files) {
    try {
      const item = await uploadOnlineMedia(editingUid.value, file);
      if (selectedEntry.value) selectedEntry.value.media = [...selectedEntry.value.media, item];
      success += 1;
    } catch (error) {
      ElMessage.error(`${file.name}：${errorMessage(error, "影像上传失败")}`);
    }
  }
  uploadingMedia.value = false;
  if (success) ElMessage.success(`已添加 ${success} 个现场影像`);
  await loadAll();
}

function openMedia(mediaUid: string) {
  if (editingUid.value) window.open(onlineMediaUrl(editingUid.value, mediaUid), "_blank");
}

function openEntryMedia(entryUid: string, mediaUid: string) {
  window.open(onlineMediaUrl(entryUid, mediaUid), "_blank");
}

async function removeMedia(mediaUid: string) {
  if (!editingUid.value) return;
  try {
    await ElMessageBox.confirm("确认删除这个现场影像吗？", "删除影像", { type: "warning" });
    await deleteOnlineMedia(editingUid.value, mediaUid);
    if (selectedEntry.value) selectedEntry.value.media = selectedEntry.value.media.filter((item) => item.media_uid !== mediaUid);
    ElMessage.success("影像已删除");
    await loadAll();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(errorMessage(error, "影像删除失败"));
  }
}

function localSubmitError(): string | null {
  const definition = selectedDefinition.value;
  if (!definition) return "请先选择调查表";
  const missingField = definition.fields.find(
    (field) => field.required && (formData.value[field.key] === undefined || String(formData.value[field.key] ?? "").trim() === ""),
  );
  if (missingField) return `请填写“${missingField.display_label}”`;
  const missingEvaluation = evaluations.value.find((item) => !item.grade);
  if (missingEvaluation) return `请完成“${missingEvaluation.item_name}”的评价`;
  if (!conclusion.survey_date) return "请选择调查日期";
  if (!conclusion.overall_grade) return "请选择总体评价";
  if (!conclusion.surveyor_signatures.trim()) return "请填写调查人员";
  if (!conclusion.survey_comment.trim()) return "请填写调查意见与建议";
  return null;
}

async function saveAndSubmit() {
  const problem = localSubmitError();
  if (problem) {
    ElMessage.warning(problem);
    return;
  }
  try {
    await ElMessageBox.confirm(
      "提交后本条记录将进入审核，审核前不能继续修改。确认提交吗？",
      "提交调查记录",
      { type: "warning", confirmButtonText: "确认提交", cancelButtonText: "继续检查" },
    );
  } catch {
    return;
  }
  const row = await saveDraft(false);
  if (!row) return;
  saving.value = true;
  try {
    await submitOnlineEntry(row.entry_uid);
    ElMessage.success("调查记录已提交审核");
    drawerVisible.value = false;
    await loadAll();
  } catch (error) {
    ElMessage.error(errorMessage(error, "提交失败，请检查必填内容"));
  } finally {
    saving.value = false;
  }
}

function openDetail(row: OnlineEntry) {
  selectedEntry.value = row;
  detailVisible.value = true;
}

async function review(row: OnlineEntry, decision: "accept" | "reject") {
  try {
    let notes: string | null = null;
    if (decision === "reject") {
      const result = await ElMessageBox.prompt(
        "请明确写出需要补充或修改的内容，录入人员将按此意见重新提交。",
        "退回修改",
        { inputPlaceholder: "填写修改意见", inputValidator: (value) => Boolean(value.trim()) || "请填写修改意见" },
      );
      notes = result.value;
    } else {
      await ElMessageBox.confirm(
        "审核通过后，本条记录将立即进入正式成果库。请确认内容真实、完整。",
        "审核通过并入库",
        { type: "success", confirmButtonText: "通过并入库" },
      );
    }
    await reviewOnlineEntry(row.entry_uid, decision, notes);
    ElMessage.success(decision === "accept" ? "审核完成，记录已进入正式成果库" : "记录已退回修改");
    await loadAll();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(errorMessage(error, "审核操作失败，请稍后重试"));
  }
}

onMounted(loadAll);
</script>

<template>
  <div class="module-header online-entry-header">
    <div>
      <div class="eyebrow">在线补录与内业填报</div>
      <h1>调查数据录入</h1>
      <p>在办公室或有网络的环境中直接填写调查记录；现场离线调查仍使用桌面端。</p>
    </div>
    <div class="header-actions">
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      <el-button v-if="canWrite" type="primary" :icon="Plus" @click="openCreate">新建调查记录</el-button>
    </div>
  </div>

  <el-alert
    class="linkage-alert"
    title="Web 与桌面端不是两套账：二者使用同一任务和基础资料，记录只有审核进入中心正式成果库后才成为正式数据。"
    type="success"
    :closable="false"
    show-icon
  />

  <div class="entry-collaboration-strip">
    <div>
      <b>桌面端录入</b>
      <span>适合现场离线采集，完成后导出成果文件并回传中心审核</span>
    </div>
    <i>→</i>
    <div class="center-truth">
      <b>中心正式成果库</b>
      <span>唯一正式依据，统一查重、审核、留痕和汇总</span>
    </div>
    <i>←</i>
    <div>
      <b>Web 在线录入</b>
      <span>适合办公室补录，提交后经审核直接进入同一正式成果库</span>
    </div>
  </div>

  <div class="entry-stat-row">
    <div><span>全部记录</span><strong>{{ entries.length }}</strong></div>
    <div><span>正在填写</span><strong>{{ entries.filter((item) => ['draft', 'rejected'].includes(item.status)).length }}</strong></div>
    <div><span>等待审核</span><strong>{{ entries.filter((item) => item.status === 'submitted').length }}</strong></div>
    <div><span>已入正式库</span><strong>{{ entries.filter((item) => item.status === 'imported').length }}</strong></div>
  </div>

  <el-card shadow="never" class="business-card entry-list-card">
    <template #header>
      <div class="card-header"><span>在线调查记录</span><small>草稿自动与调查任务关联</small></div>
    </template>
    <el-table v-loading="loading" :data="entries" stripe>
      <el-table-column label="调查对象" min-width="220">
        <template #default="{ row }">
          <div class="task-name">{{ row.asset_name || "尚未填写名称" }}</div>
          <div class="result-secondary">{{ row.form_name }}</div>
        </template>
      </el-table-column>
      <el-table-column label="所属任务" min-width="210">
        <template #default="{ row }">
          <div>{{ row.task_name }}</div>
          <div class="result-secondary">{{ row.project_name }} · {{ row.batch_name }}</div>
        </template>
      </el-table-column>
      <el-table-column label="调查范围" min-width="180">
        <template #default="{ row }">
          <div>{{ row.canal_name }}</div>
          <div class="result-secondary">{{ row.organization_name }}</div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }"><el-tag :type="statusTypes[row.status]">{{ statusLabels[row.status] }}</el-tag></template>
      </el-table-column>
      <el-table-column label="最近更新" width="175">
        <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button link :icon="View" @click="openDetail(row)">查看</el-button>
          <el-button
            v-if="canWrite && ['draft', 'rejected'].includes(row.status) && (auth.isAdmin || row.created_by_username === auth.user?.username)"
            link type="primary" :icon="Edit" @click="openEdit(row)"
          >继续填写</el-button>
          <template v-if="canReview && row.status === 'submitted'">
            <el-button link type="success" :icon="Check" @click="review(row, 'accept')">通过入库</el-button>
            <el-button link type="danger" @click="review(row, 'reject')">退回</el-button>
          </template>
        </template>
      </el-table-column>
      <template #empty>
        <div class="business-empty compact">
          <div class="business-empty-mark">录</div>
          <h3>还没有在线调查记录</h3>
          <p v-if="activeTasks.length">可以从已下发任务中选择渠道和调查表开始录入；现场无网络时仍使用桌面端采集。</p>
          <p v-else>在线录入必须关联已经下发的调查任务，请先到任务中心建立任务。</p>
          <div class="empty-actions">
            <el-button v-if="canWrite && activeTasks.length" type="primary" :icon="Plus" @click="openCreate">新建调查记录</el-button>
            <el-button v-else type="primary" @click="$router.push('/tasks')">前往任务中心</el-button>
          </div>
        </div>
      </template>
    </el-table>
  </el-card>

  <el-drawer v-model="drawerVisible" :title="editingUid ? '填写调查记录' : '新建调查记录'" size="78%" destroy-on-close>
    <div class="entry-editor">
      <el-card shadow="never" class="entry-context-card">
        <div class="entry-context-grid">
          <div>
            <label>调查任务</label>
            <el-select v-model="selector.task_uid" filterable placeholder="选择已下发的调查任务" :disabled="Boolean(editingUid)" @change="onTaskChange">
              <el-option v-for="item in activeTasks" :key="item.task_uid" :label="`${item.task_name} · ${item.organization_name}`" :value="item.task_uid" />
            </el-select>
          </div>
          <div>
            <label>调查范围</label>
            <el-select v-model="selector.management_scope_uid" filterable placeholder="选择渠道和分管范围" :disabled="Boolean(editingUid) || !selector.task_uid">
              <el-option v-for="item in scopes" :key="item.management_scope_uid" :label="`${item.canal_name} · ${item.organization_name} · ${rangeText(item)}`" :value="item.management_scope_uid" />
            </el-select>
          </div>
          <div>
            <label>调查表</label>
            <el-select v-model="selector.form_code" filterable placeholder="选择工程类型" :disabled="Boolean(editingUid)" @change="onFormChange">
              <el-option v-for="item in definitions" :key="item.form_code" :label="`附表${item.form_number} ${item.form_name}`" :value="item.form_code" />
            </el-select>
          </div>
        </div>
      </el-card>

      <el-alert v-if="activeTasks.length === 0" class="entry-review-alert" type="info" :closable="false" show-icon>
        <template #title>
          尚无可用于录入的调查任务，请先到
          <router-link to="/tasks" @click="drawerVisible = false">调查任务中心</router-link>
          新建并下发任务。
        </template>
      </el-alert>

      <el-empty v-if="!selectedDefinition" :description="activeTasks.length ? '请先选择调查任务、调查范围和调查表' : '建立调查任务后，即可在这里开始在线录入'" />

      <template v-else>
        <el-alert v-if="selectedEntry?.status === 'rejected'" class="entry-review-alert" :title="`审核意见：${selectedEntry.review_notes || '请补充完善后重新提交'}`" type="warning" :closable="false" show-icon />

        <section v-for="section in selectedDefinition.sections" :key="section.title" class="entry-form-section">
          <h3>{{ section.title }}</h3>
          <div class="entry-field-grid">
            <div v-for="row in section.rows" :key="row.field_keys.join('-')" class="entry-field-row" :class="{ wide: row.field_keys.length > 1 }">
              <template v-for="(key, index) in row.field_keys" :key="key">
                <div v-if="fieldOf(key)" class="entry-field">
                  <label>{{ fieldOf(key)?.display_label }} <i v-if="fieldOf(key)?.required">*</i></label>
                  <el-select v-if="fieldOf(key)?.input_type === 'choice'" v-model="formData[key]" clearable :placeholder="fieldOf(key)?.placeholder || '请选择'">
                    <el-option v-for="choice in fieldOf(key)?.choices" :key="choice" :label="choice" :value="choice" />
                  </el-select>
                  <el-date-picker v-else-if="fieldOf(key)?.input_type === 'month'" v-model="formData[key]" type="month" value-format="YYYY-MM" format="YYYY年MM月" placeholder="选择月份" />
                  <el-input-number v-else-if="['decimal', 'signed_decimal', 'integer'].includes(fieldOf(key)?.input_type || '')" v-model="formData[key]" :precision="fieldOf(key)?.input_type === 'integer' ? 0 : 3" :max="fieldOf(key)?.maximum ?? undefined" controls-position="right" />
                  <el-input v-else v-model="formData[key]" clearable :placeholder="fieldOf(key)?.placeholder || '请输入'" />
                </div>
                <span v-if="index < row.field_keys.length - 1" class="field-separator">{{ row.separator || "—" }}</span>
              </template>
            </div>
          </div>
        </section>

        <section class="entry-form-section evaluation-section">
          <h3>{{ selectedDefinition.evaluation_title }}</h3>
          <p v-if="selectedDefinition.evaluation_note" class="section-note">{{ selectedDefinition.evaluation_note }}</p>
          <el-table :data="evaluations" border>
            <el-table-column prop="category" label="类别" min-width="110" />
            <el-table-column prop="item_name" label="检查项目" min-width="150" />
            <el-table-column label="评价" min-width="260">
              <template #default="{ row }">
                <el-radio-group v-model="row.grade" size="small">
                  <el-radio-button v-for="grade in selectedDefinition.grade_options" :key="grade" :value="grade">{{ grade }}</el-radio-button>
                </el-radio-group>
                <div v-if="selectedStandard(row)" class="grade-standard">{{ selectedStandard(row) }}</div>
              </template>
            </el-table-column>
            <el-table-column label="现场情况说明" min-width="210">
              <template #default="{ row }"><el-input v-model="row.description" placeholder="可填写实测或观察情况" /></template>
            </el-table-column>
            <el-table-column label="备注" min-width="150">
              <template #default="{ row }"><el-input v-model="row.remark" placeholder="选填" /></template>
            </el-table-column>
          </el-table>
        </section>

        <section class="entry-form-section conclusion-section">
          <h3>{{ selectedDefinition.conclusion_title }}</h3>
          <div class="entry-field-grid">
            <div class="entry-field"><label>调查日期 <i>*</i></label><el-date-picker v-model="conclusion.survey_date" type="date" value-format="YYYY-MM-DD" format="YYYY年MM月DD日" /></div>
            <div class="entry-field"><label>总体评价 <i>*</i></label><el-select v-model="conclusion.overall_grade" placeholder="请选择"><el-option v-for="grade in selectedDefinition.grade_options" :key="grade" :label="grade" :value="grade" /></el-select></div>
            <div class="entry-field"><label>调查人员 <i>*</i></label><el-input v-model="conclusion.surveyor_signatures" placeholder="多人可用顿号分隔" /></div>
            <div class="entry-field"><label>水管所负责人</label><el-input v-model="conclusion.water_office_manager_signature" placeholder="选填" /></div>
            <div class="entry-field"><label>工程科负责人</label><el-input v-model="conclusion.engineering_section_chief_signature" placeholder="选填" /></div>
            <div class="entry-field"><label>管理处负责人</label><el-input v-model="conclusion.department_head_signature" placeholder="选填" /></div>
            <div class="entry-field full"><label>调查意见与建议 <i>*</i></label><el-input v-model="conclusion.survey_comment" type="textarea" :rows="3" placeholder="填写现场发现的问题、处置建议或需要说明的情况" /></div>
          </div>
        </section>

        <section class="entry-form-section entry-media-section">
          <div class="entry-media-heading">
            <div>
              <h3>现场照片与视频</h3>
              <p>可上传现场全貌、问题部位和处置前后对比影像；桌面端成果包中的影像也会进入同一正式成果库。</p>
            </div>
            <el-button v-if="editable" :icon="UploadFilled" :loading="uploadingMedia" @click="chooseMedia">添加照片或视频</el-button>
            <input ref="mediaInput" type="file" accept="image/*,video/*" multiple hidden @change="addSelectedMedia" />
          </div>
          <div v-if="selectedEntry?.media.length" class="entry-media-list">
            <div v-for="item in selectedEntry.media" :key="item.media_uid" class="entry-media-item">
              <span class="entry-media-kind">{{ item.media_kind === "photo" ? "照片" : "视频" }}</span>
              <div><strong>{{ item.original_filename }}</strong><small>{{ item.media_role }} · {{ formatSize(item.file_size) }}</small></div>
              <el-button link type="primary" @click="openMedia(item.media_uid)">查看</el-button>
              <el-button v-if="editable" link type="danger" @click="removeMedia(item.media_uid)">删除</el-button>
            </div>
          </div>
          <el-empty v-else description="尚未添加现场影像（不影响保存草稿）" :image-size="54" />
        </section>
      </template>
    </div>
    <template #footer>
      <div class="entry-drawer-footer">
        <span>草稿不会进入正式成果库，提交并审核通过后才会正式入库。</span>
        <div>
          <el-button @click="drawerVisible = false">关闭</el-button>
          <el-button v-if="selectedDefinition && editable" :loading="saving" @click="saveDraft(true)">保存草稿</el-button>
          <el-button v-if="selectedDefinition && editable" type="primary" :icon="UploadFilled" :loading="saving" @click="saveAndSubmit">提交审核</el-button>
        </div>
      </div>
    </template>
  </el-drawer>

  <el-drawer v-model="detailVisible" title="在线调查记录" size="620px">
    <template v-if="selectedEntry">
      <div class="task-detail-hero">
        <el-tag :type="statusTypes[selectedEntry.status]">{{ statusLabels[selectedEntry.status] }}</el-tag>
        <h2>{{ selectedEntry.asset_name || "尚未填写调查对象名称" }}</h2>
        <p>{{ selectedEntry.form_name }}</p>
      </div>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="所属任务" :span="2">{{ selectedEntry.task_name }}</el-descriptions-item>
        <el-descriptions-item label="项目批次" :span="2">{{ selectedEntry.project_name }} · {{ selectedEntry.batch_name }}</el-descriptions-item>
        <el-descriptions-item label="管理单位">{{ selectedEntry.organization_name }}</el-descriptions-item>
        <el-descriptions-item label="渠道">{{ selectedEntry.canal_name }}</el-descriptions-item>
        <el-descriptions-item label="录入人员">{{ selectedEntry.created_by_username }}</el-descriptions-item>
        <el-descriptions-item label="最近更新">{{ formatTime(selectedEntry.updated_at) }}</el-descriptions-item>
        <el-descriptions-item v-if="selectedEntry.review_notes" label="审核意见" :span="2">{{ selectedEntry.review_notes }}</el-descriptions-item>
      </el-descriptions>
      <el-alert v-if="selectedEntry.status === 'imported'" class="entry-review-alert" title="该记录已审核通过并进入正式成果库，可在“正式成果库”中查询。" type="success" :closable="false" show-icon />
      <h3 class="drawer-section-title">现场照片与视频（{{ selectedEntry.media.length }}）</h3>
      <div v-if="selectedEntry.media.length" class="entry-media-list">
        <div v-for="item in selectedEntry.media" :key="item.media_uid" class="entry-media-item">
          <span class="entry-media-kind">{{ item.media_kind === "photo" ? "照片" : "视频" }}</span>
          <div><strong>{{ item.original_filename }}</strong><small>{{ formatSize(item.file_size) }}</small></div>
          <el-button link type="primary" @click="openEntryMedia(selectedEntry.entry_uid, item.media_uid)">查看</el-button>
        </div>
      </div>
    </template>
  </el-drawer>
</template>
