<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { Delete, Download, Edit, Plus, Refresh, Search, SwitchButton } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  changeMasterItemStatus,
  createMasterItem,
  deleteMasterItem,
  getMasterDataSnapshot,
  masterDataExportUrl,
  updateMasterItem,
  type Canal,
  type Department,
  type ManagementScope,
  type MasterDataSnapshot,
  type MasterKind,
  type Office,
} from "../api/masterData";
import { useAuthStore } from "../stores/auth";

type MasterRow = Department | Office | Canal | ManagementScope;

const auth = useAuthStore();
const loading = ref(false);
const saving = ref(false);
const snapshot = ref<MasterDataSnapshot | null>(null);
const activeTab = ref<MasterKind>("departments");
const keyword = ref("");
const showInactive = ref(true);
const dialogVisible = ref(false);
const editingUid = ref("");
const form = reactive({
  name: "",
  business_code: "",
  parent_department_uid: "",
  canal_level: "03" as "01" | "02" | "03" | "04",
  parent_canal_uid: "",
  canal_uid: "",
  organization_unit_uid: "",
  range_mode: "whole" as "whole" | "segment_known" | "segment_unknown",
  start_stake_text: "",
  end_stake_text: "",
  sort_order: 0,
  description: "",
});

const canWrite = computed(() => auth.hasPermission("master_data.write"));
const normalizedKeyword = computed(() => keyword.value.trim().toLowerCase());
const includesKeyword = (...values: Array<string | null | undefined>) => {
  const query = normalizedKeyword.value;
  return !query || values.some((value) => value?.toLowerCase().includes(query));
};
const visible = <T extends { status: string }>(items: T[]) => items.filter((item) => showInactive.value || item.status === "active");
const departments = computed(() => visible(snapshot.value?.departments ?? []).filter((item) => includesKeyword(item.name, item.business_code)));
const offices = computed(() => visible(snapshot.value?.offices ?? []).filter((item) => includesKeyword(item.name, item.parent_name, item.business_code)));
const canals = computed(() => visible(snapshot.value?.canals ?? []).filter((item) => includesKeyword(item.name, item.parent_name, levelLabel(item.canal_level))));
const scopes = computed(() => visible(snapshot.value?.management_scopes ?? []).filter((item) => includesKeyword(item.canal_name, item.organization_name, item.description)));
const activeDepartments = computed(() => (snapshot.value?.departments ?? []).filter((item) => item.status === "active"));
const activeOffices = computed(() => (snapshot.value?.offices ?? []).filter((item) => item.status === "active"));
const activeCanals = computed(() => (snapshot.value?.canals ?? []).filter((item) => item.status === "active"));

const tabNames: Record<MasterKind, string> = { departments: "管理处", offices: "管理所", canals: "渠道", scopes: "分管范围" };
const levelNames: Record<string, string> = { "01": "干渠", "02": "分干渠", "03": "支渠", "04": "分支渠" };
const rangeNames: Record<string, string> = { whole: "全渠管理", segment_known: "按已知桩号分段", segment_unknown: "分段管理（边界待确认）" };

function levelLabel(value: string) { return levelNames[value] ?? value; }
function scopeRange(item: ManagementScope) {
  if (item.range_mode === "whole") return "全渠";
  if (item.range_mode === "segment_unknown") return "分段，边界待确认";
  return `${item.start_stake_text ?? "-"} — ${item.end_stake_text ?? "-"}`;
}
function statusLabel(status: string) { return status === "active" ? "启用" : "停用"; }
function errorMessage(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return typeof detail === "string" && detail ? detail : fallback;
}

async function loadData() {
  loading.value = true;
  try { snapshot.value = await getMasterDataSnapshot(); }
  catch { ElMessage.error("基础资料加载失败，请稍后重试；如问题持续，请联系系统管理员"); }
  finally { loading.value = false; }
}

function resetForm() {
  Object.assign(form, { name: "", business_code: "", parent_department_uid: "", canal_level: "03", parent_canal_uid: "", canal_uid: "", organization_unit_uid: "", range_mode: "whole", start_stake_text: "", end_stake_text: "", sort_order: 0, description: "" });
}

function openCreate() {
  editingUid.value = "";
  resetForm();
  if (activeTab.value === "offices") form.parent_department_uid = activeDepartments.value[0]?.stable_uid ?? "";
  if (activeTab.value === "scopes") {
    form.canal_uid = activeCanals.value[0]?.stable_uid ?? "";
    form.organization_unit_uid = activeOffices.value[0]?.stable_uid ?? "";
  }
  dialogVisible.value = true;
}

function openEdit(row: MasterRow) {
  editingUid.value = row.stable_uid;
  resetForm();
  form.sort_order = row.sort_order;
  form.description = row.description ?? "";
  if (activeTab.value === "departments") {
    const item = row as Department; form.name = item.name; form.business_code = item.business_code;
  } else if (activeTab.value === "offices") {
    const item = row as Office; form.name = item.name; form.business_code = item.business_code;
    form.parent_department_uid = snapshot.value?.departments.find((value) => value.master_key === item.parent_master_key)?.stable_uid ?? "";
  } else if (activeTab.value === "canals") {
    const item = row as Canal; form.name = item.name; form.canal_level = item.canal_level as typeof form.canal_level;
    form.parent_canal_uid = snapshot.value?.canals.find((value) => value.master_key === item.parent_master_key)?.stable_uid ?? "";
  } else {
    const item = row as ManagementScope;
    form.canal_uid = snapshot.value?.canals.find((value) => value.master_key === item.canal_master_key)?.stable_uid ?? "";
    form.organization_unit_uid = snapshot.value?.offices.find((value) => value.master_key === item.organization_master_key)?.stable_uid ?? "";
    form.range_mode = item.range_mode; form.start_stake_text = item.start_stake_text ?? ""; form.end_stake_text = item.end_stake_text ?? "";
  }
  dialogVisible.value = true;
}

function payload() {
  const common = { sort_order: form.sort_order, description: form.description.trim() || null };
  if (activeTab.value === "departments") return { ...common, name: form.name.trim(), business_code: form.business_code.trim() };
  if (activeTab.value === "offices") return { ...common, name: form.name.trim(), business_code: form.business_code.trim(), parent_department_uid: form.parent_department_uid };
  if (activeTab.value === "canals") return { ...common, name: form.name.trim(), canal_level: form.canal_level, parent_canal_uid: form.parent_canal_uid || null };
  return { ...common, canal_uid: form.canal_uid, organization_unit_uid: form.organization_unit_uid, range_mode: form.range_mode, start_stake_text: form.range_mode === "segment_known" ? form.start_stake_text.trim() || null : null, end_stake_text: form.range_mode === "segment_known" ? form.end_stake_text.trim() || null : null };
}

function validateForm(): string | null {
  if (["departments", "offices", "canals"].includes(activeTab.value) && !form.name.trim()) return "请填写名称";
  if (["departments", "offices"].includes(activeTab.value) && !form.business_code.trim()) return "请填写业务编码";
  if (activeTab.value === "offices" && !form.parent_department_uid) return "请选择所属管理处";
  if (activeTab.value === "scopes" && (!form.canal_uid || !form.organization_unit_uid)) return "请选择渠道和管理所";
  if (activeTab.value === "scopes" && form.range_mode === "segment_known" && (!form.start_stake_text.trim() || !form.end_stake_text.trim())) return "请填写完整的起止桩号";
  return null;
}

async function save() {
  const problem = validateForm(); if (problem) { ElMessage.warning(problem); return; }
  saving.value = true;
  try {
    if (editingUid.value) await updateMasterItem(activeTab.value, editingUid.value, payload());
    else await createMasterItem(activeTab.value, payload());
    ElMessage.success(`${tabNames[activeTab.value]}已保存，新的基础资料版本已生效`);
    dialogVisible.value = false; await loadData();
  } catch (error) { ElMessage.error(errorMessage(error, "保存失败，请检查填写内容")); }
  finally { saving.value = false; }
}

async function toggleStatus(row: MasterRow) {
  const target = row.status === "active" ? "inactive" : "active";
  try {
    await ElMessageBox.confirm(target === "inactive" ? "停用后不能用于新任务，但历史任务和成果仍会保留。确认停用吗？" : "确认重新启用这条基础资料吗？", target === "inactive" ? "停用基础资料" : "启用基础资料", { type: "warning" });
    await changeMasterItemStatus(activeTab.value, row.stable_uid, target);
    ElMessage.success(target === "active" ? "已启用" : "已停用"); await loadData();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(errorMessage(error, "状态调整失败"));
  }
}

async function remove(row: MasterRow) {
  try {
    await ElMessageBox.confirm("只允许删除已经停用且从未被任务或成果使用的资料。删除后无法恢复，是否继续？", "删除基础资料", { type: "error", confirmButtonText: "确认删除" });
    await deleteMasterItem(activeTab.value, row.stable_uid);
    ElMessage.success("基础资料已删除"); await loadData();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(errorMessage(error, "删除失败"));
  }
}

function exportSnapshot() { window.open(masterDataExportUrl(), "_blank"); }
onMounted(loadData);
</script>

<template>
  <div class="module-header master-header">
    <div>
      <div class="eyebrow">全系统唯一正式依据</div>
      <h1>基础资料</h1>
      <p>管理处、管理所、渠道和分管范围在中心统一维护；新任务自动携带当时的正式版本供桌面端使用。</p>
    </div>
    <div class="header-actions">
      <el-input v-model="keyword" :prefix-icon="Search" clearable placeholder="搜索名称或业务编码" class="master-search" />
      <el-button :icon="Download" @click="exportSnapshot">导出当前版本</el-button>
      <el-button :icon="Refresh" :loading="loading" @click="loadData">刷新</el-button>
      <el-button v-if="canWrite" type="primary" :icon="Plus" @click="openCreate">新增{{ tabNames[activeTab] }}</el-button>
    </div>
  </div>

  <el-alert class="linkage-alert" title="基础资料修改后只影响新建任务；已经下发到桌面端的任务继续使用原版本快照，保证历史调查可追溯。需要采用新资料时，请重新下发任务。" type="success" :closable="false" show-icon />
  <el-skeleton v-if="loading && !snapshot" :rows="8" animated />

  <template v-else-if="snapshot">
    <div class="master-summary-grid">
      <div class="summary-tile blue"><span>管理处</span><strong>{{ snapshot.summary.department_count }}</strong></div>
      <div class="summary-tile cyan"><span>管理所</span><strong>{{ snapshot.summary.office_count }}</strong></div>
      <div class="summary-tile violet"><span>渠道</span><strong>{{ snapshot.summary.canal_count }}</strong></div>
      <div class="summary-tile amber"><span>分管范围</span><strong>{{ snapshot.summary.management_scope_count }}</strong></div>
    </div>

    <el-card shadow="never" class="business-card master-card">
      <div class="contract-strip">
        <div><span class="contract-label">当前正式版本</span><strong>{{ snapshot.summary.master_data_version }}</strong></div>
        <div><span class="contract-label">版本用途</span><strong>新任务下发和 Web 在线录入</strong></div>
        <el-checkbox v-model="showInactive">显示停用资料</el-checkbox>
        <el-tag type="success" effect="light">中心统一管理</el-tag>
      </div>

      <el-tabs v-model="activeTab" class="master-tabs">
        <el-tab-pane :label="`管理处 ${departments.length}`" name="departments">
          <el-table :data="departments" stripe height="520">
            <el-table-column prop="name" label="管理处名称" min-width="180" />
            <el-table-column prop="business_code" label="业务编码" width="120" />
            <el-table-column prop="sort_order" label="顺序" width="80" align="center" />
            <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
            <el-table-column v-if="canWrite" label="操作" width="220" fixed="right"><template #default="{ row }"><el-button link :icon="Edit" @click="openEdit(row)">修改</el-button><el-button link :icon="SwitchButton" @click="toggleStatus(row)">{{ row.status === 'active' ? '停用' : '启用' }}</el-button><el-button v-if="row.status === 'inactive'" link type="danger" :icon="Delete" @click="remove(row)">删除</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`管理所 ${offices.length}`" name="offices">
          <el-table :data="offices" stripe height="520">
            <el-table-column prop="name" label="管理所名称" min-width="180" />
            <el-table-column prop="parent_name" label="所属管理处" min-width="170" />
            <el-table-column prop="business_code" label="业务编码" width="120" />
            <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
            <el-table-column v-if="canWrite" label="操作" width="220" fixed="right"><template #default="{ row }"><el-button link :icon="Edit" @click="openEdit(row)">修改</el-button><el-button link :icon="SwitchButton" @click="toggleStatus(row)">{{ row.status === 'active' ? '停用' : '启用' }}</el-button><el-button v-if="row.status === 'inactive'" link type="danger" :icon="Delete" @click="remove(row)">删除</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`渠道 ${canals.length}`" name="canals">
          <el-table :data="canals" stripe height="520">
            <el-table-column prop="name" label="渠道名称" min-width="180" />
            <el-table-column label="层级" width="110"><template #default="{ row }"><el-tag size="small" effect="plain">{{ levelLabel(row.canal_level) }}</el-tag></template></el-table-column>
            <el-table-column prop="parent_name" label="上级渠道" min-width="160"><template #default="{ row }">{{ row.parent_name ?? "—" }}</template></el-table-column>
            <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
            <el-table-column v-if="canWrite" label="操作" width="220" fixed="right"><template #default="{ row }"><el-button link :icon="Edit" @click="openEdit(row)">修改</el-button><el-button link :icon="SwitchButton" @click="toggleStatus(row)">{{ row.status === 'active' ? '停用' : '启用' }}</el-button><el-button v-if="row.status === 'inactive'" link type="danger" :icon="Delete" @click="remove(row)">删除</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`分管范围 ${scopes.length}`" name="scopes">
          <el-table :data="scopes" stripe height="520">
            <el-table-column prop="canal_name" label="渠道" min-width="160" />
            <el-table-column prop="organization_name" label="管理所" min-width="170" />
            <el-table-column label="管理方式" min-width="150"><template #default="{ row }">{{ rangeNames[row.range_mode] }}</template></el-table-column>
            <el-table-column label="管理区间" min-width="190"><template #default="{ row }">{{ scopeRange(row) }}</template></el-table-column>
            <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
            <el-table-column v-if="canWrite" label="操作" width="220" fixed="right"><template #default="{ row }"><el-button link :icon="Edit" @click="openEdit(row)">修改</el-button><el-button link :icon="SwitchButton" @click="toggleStatus(row)">{{ row.status === 'active' ? '停用' : '启用' }}</el-button><el-button v-if="row.status === 'inactive'" link type="danger" :icon="Delete" @click="remove(row)">删除</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </template>

  <el-dialog v-model="dialogVisible" :title="`${editingUid ? '修改' : '新增'}${tabNames[activeTab]}`" width="680px" destroy-on-close>
    <el-alert v-if="activeTab === 'scopes'" title="同一条渠道可按桩号划分给多个管理所；系统会阻止分管区间相互重叠。" type="info" :closable="false" show-icon />
    <el-form label-position="top" class="master-edit-form">
      <template v-if="activeTab === 'departments' || activeTab === 'offices'">
        <el-form-item v-if="activeTab === 'offices'" label="所属管理处"><el-select v-model="form.parent_department_uid" filterable><el-option v-for="item in activeDepartments" :key="item.stable_uid" :label="item.name" :value="item.stable_uid" /></el-select></el-form-item>
        <div class="two-column-form"><el-form-item label="名称"><el-input v-model="form.name" /></el-form-item><el-form-item label="业务编码"><el-input v-model="form.business_code" /></el-form-item></div>
      </template>
      <template v-else-if="activeTab === 'canals'">
        <div class="two-column-form"><el-form-item label="渠道名称"><el-input v-model="form.name" /></el-form-item><el-form-item label="渠道层级"><el-select v-model="form.canal_level"><el-option v-for="(label, value) in levelNames" :key="value" :label="label" :value="value" /></el-select></el-form-item></div>
        <el-form-item label="上级渠道（干渠或独立渠道可不选）"><el-select v-model="form.parent_canal_uid" clearable filterable><el-option v-for="item in activeCanals.filter((value) => value.stable_uid !== editingUid)" :key="item.stable_uid" :label="item.name" :value="item.stable_uid" /></el-select></el-form-item>
      </template>
      <template v-else>
        <div class="two-column-form"><el-form-item label="渠道"><el-select v-model="form.canal_uid" filterable><el-option v-for="item in activeCanals" :key="item.stable_uid" :label="item.name" :value="item.stable_uid" /></el-select></el-form-item><el-form-item label="负责管理所"><el-select v-model="form.organization_unit_uid" filterable><el-option v-for="item in activeOffices" :key="item.stable_uid" :label="`${item.name} · ${item.parent_name}`" :value="item.stable_uid" /></el-select></el-form-item></div>
        <el-form-item label="管理方式"><el-radio-group v-model="form.range_mode"><el-radio-button value="whole">全渠管理</el-radio-button><el-radio-button value="segment_known">按桩号分段</el-radio-button><el-radio-button value="segment_unknown">边界待确认</el-radio-button></el-radio-group></el-form-item>
        <div v-if="form.range_mode === 'segment_known'" class="two-column-form"><el-form-item label="起始桩号"><el-input v-model="form.start_stake_text" placeholder="例如 CH12+000" /></el-form-item><el-form-item label="终止桩号"><el-input v-model="form.end_stake_text" placeholder="例如 CH18+500" /></el-form-item></div>
      </template>
      <div class="two-column-form"><el-form-item label="显示顺序"><el-input-number v-model="form.sort_order" :min="0" controls-position="right" /></el-form-item></div>
      <el-form-item label="说明（选填）"><el-input v-model="form.description" type="textarea" :rows="3" maxlength="2000" show-word-limit /></el-form-item>
    </el-form>
    <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存并形成新版本</el-button></template>
  </el-dialog>
</template>
