<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from "vue";
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

type PrimarySection = "departments" | "offices" | "canals";
type MasterRow = Department | Office | Canal | ManagementScope;

const auth = useAuthStore();
const loading = ref(false);
const saving = ref(false);
const snapshot = ref<MasterDataSnapshot | null>(null);
const activeSection = ref<PrimarySection>("canals");
const editingKind = ref<MasterKind>("canals");
const keyword = ref("");
const showInactive = ref(true);
const canalView = ref<"all" | "backbone" | "unassigned">("all");
const dialogVisible = ref(false);
const scopeDrawerVisible = ref(false);
const selectedCanal = ref<Canal | null>(null);
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
const allDepartments = computed(() => snapshot.value?.departments ?? []);
const allOffices = computed(() => snapshot.value?.offices ?? []);
const allCanals = computed(() => snapshot.value?.canals ?? []);
const allScopes = computed(() => snapshot.value?.management_scopes ?? []);
const activeDepartments = computed(() => allDepartments.value.filter((item) => item.status === "active"));
const activeOffices = computed(() => allOffices.value.filter((item) => item.status === "active"));
const activeCanals = computed(() => allCanals.value.filter((item) => item.status === "active"));
const includesKeyword = (...values: Array<string | null | undefined>) => {
  const query = normalizedKeyword.value;
  return !query || values.some((value) => value?.toLowerCase().includes(query));
};
const visible = <T extends { status: string }>(items: T[]) => items.filter((item) => showInactive.value || item.status === "active");
const departments = computed(() => visible(allDepartments.value).filter((item) => includesKeyword(item.name, item.business_code)));
const offices = computed(() => visible(allOffices.value).filter((item) => includesKeyword(item.name, item.parent_name, item.business_code)));

const scopesByCanal = computed(() => {
  const groups = new Map<string, ManagementScope[]>();
  for (const scope of allScopes.value) {
    const existing = groups.get(scope.canal_master_key) ?? [];
    existing.push(scope);
    groups.set(scope.canal_master_key, existing);
  }
  return groups;
});
const activeScopesFor = (canal: Canal) => (scopesByCanal.value.get(canal.master_key) ?? []).filter((item) => item.status === "active");
const backboneCanals = computed(() => activeCanals.value.filter((item) => ["01", "02"].includes(item.canal_level)));
const unassignedBackboneCanals = computed(() => backboneCanals.value.filter((item) => activeScopesFor(item).length === 0));
const canals = computed(() => visible(allCanals.value).filter((item) => {
  if (!includesKeyword(item.name, item.parent_name, levelLabel(item.canal_level), scopeSummary(item))) return false;
  if (canalView.value === "backbone") return ["01", "02"].includes(item.canal_level);
  if (canalView.value === "unassigned") return ["01", "02"].includes(item.canal_level) && activeScopesFor(item).length === 0;
  return true;
}));
const selectedScopes = computed(() => {
  if (!selectedCanal.value) return [];
  return visible(scopesByCanal.value.get(selectedCanal.value.master_key) ?? []);
});

const sectionNames: Record<PrimarySection, string> = { departments: "管理处", offices: "管理所", canals: "渠系与分管" };
const kindNames: Record<MasterKind, string> = { departments: "管理处", offices: "管理所", canals: "渠道", scopes: "分管段" };
const levelNames: Record<string, string> = { "01": "干渠", "02": "分干渠", "03": "支渠", "04": "分支渠" };
const rangeNames: Record<string, string> = { whole: "全渠管理", segment_known: "按桩号分段", segment_unknown: "分段管理（边界待确认）" };

function levelLabel(value: string) { return levelNames[value] ?? value; }
function scopeRange(item: ManagementScope) {
  if (item.range_mode === "whole") return "全渠";
  if (item.range_mode === "segment_unknown") return "分段，边界待确认";
  return `${item.start_stake_text ?? "-"} — ${item.end_stake_text ?? "-"}`;
}
function scopeSummary(canal: Canal) {
  const scopes = activeScopesFor(canal);
  if (!scopes.length) return "尚未设置分管所";
  if (scopes.length === 1) return `${scopes[0].organization_name} · ${scopeRange(scopes[0])}`;
  return `${scopes.length} 个分管段 · ${new Set(scopes.map((item) => item.organization_name)).size} 个管理所`;
}
function statusLabel(status: string) { return status === "active" ? "启用" : "停用"; }
function errorMessage(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return typeof detail === "string" && detail ? detail : fallback;
}

async function loadData() {
  loading.value = true;
  try { snapshot.value = await getMasterDataSnapshot(); }
  catch { ElMessage.error("资料加载失败，请稍后重试；如问题持续，请联系系统管理员"); }
  finally { loading.value = false; }
}

function resetForm() {
  Object.assign(form, { name: "", business_code: "", parent_department_uid: "", canal_level: "03", parent_canal_uid: "", canal_uid: "", organization_unit_uid: "", range_mode: "whole", start_stake_text: "", end_stake_text: "", sort_order: 0, description: "" });
}
function openCreate(kind: PrimarySection) {
  editingKind.value = kind;
  editingUid.value = "";
  resetForm();
  if (kind === "offices") form.parent_department_uid = activeDepartments.value[0]?.stable_uid ?? "";
  dialogVisible.value = true;
}
function openEdit(kind: PrimarySection, row: MasterRow) {
  editingKind.value = kind;
  editingUid.value = row.stable_uid;
  resetForm();
  form.sort_order = row.sort_order;
  form.description = row.description ?? "";
  if (kind === "departments") {
    const item = row as Department; form.name = item.name; form.business_code = item.business_code;
  } else if (kind === "offices") {
    const item = row as Office; form.name = item.name; form.business_code = item.business_code;
    form.parent_department_uid = allDepartments.value.find((value) => value.master_key === item.parent_master_key)?.stable_uid ?? "";
  } else {
    const item = row as Canal; form.name = item.name; form.canal_level = item.canal_level as typeof form.canal_level;
    form.parent_canal_uid = allCanals.value.find((value) => value.master_key === item.parent_master_key)?.stable_uid ?? "";
  }
  dialogVisible.value = true;
}
async function openScopeManager(canal: Canal) {
  scopeDrawerVisible.value = false;
  selectedCanal.value = { ...canal };
  await nextTick();
  scopeDrawerVisible.value = true;
}
function openCreateScope() {
  if (!selectedCanal.value) return;
  editingKind.value = "scopes";
  editingUid.value = "";
  resetForm();
  form.canal_uid = selectedCanal.value.stable_uid;
  form.organization_unit_uid = activeOffices.value[0]?.stable_uid ?? "";
  form.range_mode = ["01", "02"].includes(selectedCanal.value.canal_level) ? "segment_unknown" : "whole";
  dialogVisible.value = true;
}
function openEditScope(row: ManagementScope) {
  editingKind.value = "scopes";
  editingUid.value = row.stable_uid;
  resetForm();
  form.canal_uid = selectedCanal.value?.stable_uid ?? "";
  form.organization_unit_uid = allOffices.value.find((value) => value.master_key === row.organization_master_key)?.stable_uid ?? "";
  form.range_mode = row.range_mode;
  form.start_stake_text = row.start_stake_text ?? "";
  form.end_stake_text = row.end_stake_text ?? "";
  form.sort_order = row.sort_order;
  form.description = row.description ?? "";
  dialogVisible.value = true;
}
function showUnassignedBackbones() {
  activeSection.value = "canals";
  canalView.value = "unassigned";
}

function payload() {
  const common = { sort_order: form.sort_order, description: form.description.trim() || null };
  if (editingKind.value === "departments") return { ...common, name: form.name.trim(), business_code: form.business_code.trim() };
  if (editingKind.value === "offices") return { ...common, name: form.name.trim(), business_code: form.business_code.trim(), parent_department_uid: form.parent_department_uid };
  if (editingKind.value === "canals") return { ...common, name: form.name.trim(), canal_level: form.canal_level, parent_canal_uid: form.parent_canal_uid || null };
  return { ...common, canal_uid: form.canal_uid, organization_unit_uid: form.organization_unit_uid, range_mode: form.range_mode, start_stake_text: form.range_mode === "segment_known" ? form.start_stake_text.trim() || null : null, end_stake_text: form.range_mode === "segment_known" ? form.end_stake_text.trim() || null : null };
}
function validateForm(): string | null {
  if (["departments", "offices", "canals"].includes(editingKind.value) && !form.name.trim()) return "请填写名称";
  if (["departments", "offices"].includes(editingKind.value) && !form.business_code.trim()) return "请填写业务编码";
  if (editingKind.value === "offices" && !form.parent_department_uid) return "请选择所属管理处";
  if (editingKind.value === "scopes" && (!form.canal_uid || !form.organization_unit_uid)) return "请选择负责管理所";
  if (editingKind.value === "scopes" && form.range_mode === "segment_known" && (!form.start_stake_text.trim() || !form.end_stake_text.trim())) return "请填写完整的起止桩号";
  return null;
}
async function save() {
  const problem = validateForm(); if (problem) { ElMessage.warning(problem); return; }
  saving.value = true;
  try {
    if (editingUid.value) await updateMasterItem(editingKind.value, editingUid.value, payload());
    else await createMasterItem(editingKind.value, payload());
    ElMessage.success(`${kindNames[editingKind.value]}已保存，新的正式版本已生效`);
    dialogVisible.value = false;
    await loadData();
  } catch (error) { ElMessage.error(errorMessage(error, "保存失败，请检查填写内容")); }
  finally { saving.value = false; }
}
async function toggleStatus(kind: MasterKind, row: MasterRow) {
  const target = row.status === "active" ? "inactive" : "active";
  try {
    await ElMessageBox.confirm(target === "inactive" ? "停用后不能用于新任务，但历史任务和成果仍会保留。确认停用吗？" : "确认重新启用这条资料吗？", target === "inactive" ? "确认停用" : "确认启用", { type: "warning" });
    await changeMasterItemStatus(kind, row.stable_uid, target);
    ElMessage.success(target === "active" ? "已启用" : "已停用"); await loadData();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(errorMessage(error, "状态调整失败"));
  }
}
async function remove(kind: MasterKind, row: MasterRow) {
  try {
    await ElMessageBox.confirm("只允许删除已经停用且从未被任务或成果使用的资料。删除后无法恢复，是否继续？", "确认删除", { type: "error", confirmButtonText: "确认删除" });
    await deleteMasterItem(kind, row.stable_uid);
    ElMessage.success("资料已删除"); await loadData();
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
      <div class="eyebrow">调查工作共同使用的一套资料</div>
      <h1>单位与渠系</h1>
      <p>先维护管理处和管理所，再为每条渠道设置负责单位；Web 与桌面端下发任务时共同使用这里的正式版本。</p>
    </div>
    <div class="header-actions">
      <el-input v-model="keyword" :prefix-icon="Search" clearable placeholder="搜索名称、编码或管理所" class="master-search" />
      <el-button :icon="Download" @click="exportSnapshot">导出留档</el-button>
      <el-button :icon="Refresh" :loading="loading" @click="loadData">刷新</el-button>
    </div>
  </div>

  <el-alert class="linkage-alert" title="这里是 Web 与桌面端共同使用的正式资料。已下发任务保留原版本，资料调整后需要新建或重新下发任务，避免调查过程中口径变化。" type="success" :closable="false" show-icon />
  <el-skeleton v-if="loading && !snapshot" :rows="8" animated />

  <template v-else-if="snapshot">
    <div class="master-status-strip">
      <div><span>当前正式版本</span><strong>{{ snapshot.summary.master_data_version }}</strong></div>
      <div><span>资料规模</span><strong>{{ snapshot.summary.department_count }} 个管理处 · {{ snapshot.summary.office_count }} 个管理所 · {{ snapshot.summary.canal_count }} 条渠道</strong></div>
      <button v-if="unassignedBackboneCanals.length" class="backbone-warning" type="button" @click="showUnassignedBackbones">
        <b>{{ unassignedBackboneCanals.length }}</b><span>条骨干渠待设置分管所</span>
      </button>
      <div v-else class="backbone-complete">骨干渠分管已设置完整</div>
    </div>

    <div class="master-workspace">
      <nav class="master-section-nav" aria-label="单位与渠系维护步骤">
        <button :class="{ active: activeSection === 'departments' }" @click="activeSection = 'departments'"><b>1</b><span><strong>管理处</strong><small>{{ allDepartments.length }} 条资料</small></span></button>
        <button :class="{ active: activeSection === 'offices' }" @click="activeSection = 'offices'"><b>2</b><span><strong>管理所</strong><small>{{ allOffices.length }} 条资料</small></span></button>
        <button :class="{ active: activeSection === 'canals' }" @click="activeSection = 'canals'"><b>3</b><span><strong>渠系与分管</strong><small>{{ allCanals.length }} 条渠道</small></span></button>
        <div class="nav-help">按左侧顺序维护即可。分管所直接在渠道行内设置，不再单独寻找入口。</div>
      </nav>

      <el-card shadow="never" class="business-card master-main-card">
        <div class="master-list-toolbar">
          <div><span class="eyebrow">第 {{ activeSection === 'departments' ? 1 : activeSection === 'offices' ? 2 : 3 }} 步</span><h2>{{ sectionNames[activeSection] }}</h2></div>
          <div class="master-list-actions">
            <el-checkbox v-model="showInactive">显示停用资料</el-checkbox>
            <el-button v-if="canWrite" type="primary" :icon="Plus" @click="openCreate(activeSection)">新增{{ activeSection === 'canals' ? '渠道' : sectionNames[activeSection] }}</el-button>
          </div>
        </div>

        <el-table v-if="activeSection === 'departments'" :data="departments" stripe height="560">
          <el-table-column prop="name" label="管理处名称" min-width="180" />
          <el-table-column prop="business_code" label="业务编码" width="130" />
          <el-table-column prop="description" label="说明" min-width="180"><template #default="{ row }">{{ row.description || "—" }}</template></el-table-column>
          <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
          <el-table-column v-if="canWrite" label="操作" width="220" fixed="right"><template #default="{ row }"><el-button link :icon="Edit" @click="openEdit('departments', row)">修改</el-button><el-button link :icon="SwitchButton" @click="toggleStatus('departments', row)">{{ row.status === 'active' ? '停用' : '启用' }}</el-button><el-button v-if="row.status === 'inactive'" link type="danger" :icon="Delete" @click="remove('departments', row)">删除</el-button></template></el-table-column>
        </el-table>

        <el-table v-else-if="activeSection === 'offices'" :data="offices" stripe height="560">
          <el-table-column prop="name" label="管理所名称" min-width="180" />
          <el-table-column prop="parent_name" label="所属管理处" min-width="170" />
          <el-table-column prop="business_code" label="业务编码" width="130" />
          <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
          <el-table-column v-if="canWrite" label="操作" width="220" fixed="right"><template #default="{ row }"><el-button link :icon="Edit" @click="openEdit('offices', row)">修改</el-button><el-button link :icon="SwitchButton" @click="toggleStatus('offices', row)">{{ row.status === 'active' ? '停用' : '启用' }}</el-button><el-button v-if="row.status === 'inactive'" link type="danger" :icon="Delete" @click="remove('offices', row)">删除</el-button></template></el-table-column>
        </el-table>

        <template v-else>
          <div class="canal-view-filter">
            <el-segmented v-model="canalView" :options="[{ label: '全部渠道', value: 'all' }, { label: '干渠与分干渠', value: 'backbone' }, { label: `待设置分管（${unassignedBackboneCanals.length}）`, value: 'unassigned' }]" />
            <span>干渠、分干渠、支渠都可以由多个管理所分段负责。</span>
          </div>
          <el-table :data="canals" stripe height="510">
            <el-table-column label="渠道" min-width="180"><template #default="{ row }"><div class="canal-name-cell"><strong>{{ row.name }}</strong><span>{{ row.parent_name ? `上级：${row.parent_name}` : "骨干渠道" }}</span></div></template></el-table-column>
            <el-table-column label="类型" width="105"><template #default="{ row }"><el-tag size="small" effect="plain">{{ levelLabel(row.canal_level) }}</el-tag></template></el-table-column>
            <el-table-column label="分管所与区段" min-width="260"><template #default="{ row }"><button class="scope-summary-button" :class="{ missing: activeScopesFor(row).length === 0 }" type="button" @click="openScopeManager(row)"><strong>{{ scopeSummary(row) }}</strong><span>{{ activeScopesFor(row).length ? '查看或调整分管段' : '现在设置' }}</span></button></template></el-table-column>
            <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
            <el-table-column label="操作" width="270" fixed="right"><template #default="{ row }"><el-button type="primary" link @click="openScopeManager(row)">管理分管所</el-button><template v-if="canWrite"><el-button link :icon="Edit" @click="openEdit('canals', row)">修改渠道</el-button><el-dropdown trigger="click"><el-button link>更多</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item @click="toggleStatus('canals', row)">{{ row.status === 'active' ? '停用渠道' : '启用渠道' }}</el-dropdown-item><el-dropdown-item v-if="row.status === 'inactive'" divided @click="remove('canals', row)">删除渠道</el-dropdown-item></el-dropdown-menu></template></el-dropdown></template></template></el-table-column>
          </el-table>
        </template>
      </el-card>
    </div>
  </template>

  <el-drawer v-model="scopeDrawerVisible" size="680px" destroy-on-close>
    <template #header><div><div class="eyebrow">渠道分管设置</div><h2>{{ selectedCanal?.name }}</h2></div></template>
    <div v-if="selectedCanal" class="scope-drawer-intro">
      <div class="scope-guidance"><b>{{ levelLabel(selectedCanal.canal_level) }}</b><span>同一条渠道可以分给多个管理所。桩号已明确时按起止桩号填写；暂未核实边界时先标记“边界待确认”，以后再补齐。</span></div>
      <div class="scope-drawer-toolbar"><span>当前 {{ selectedScopes.length }} 条分管记录</span><el-button v-if="canWrite" type="primary" :icon="Plus" @click="openCreateScope">新增分管段</el-button></div>
      <el-table :data="selectedScopes" stripe empty-text="尚未设置分管所">
        <el-table-column prop="organization_name" label="负责管理所" min-width="150" />
        <el-table-column label="管理区段" min-width="190"><template #default="{ row }"><strong>{{ scopeRange(row) }}</strong><div class="table-subtext">{{ rangeNames[row.range_mode] }}</div></template></el-table-column>
        <el-table-column label="状态" width="80"><template #default="{ row }"><el-tag size="small" :type="row.status === 'active' ? 'success' : 'info'">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
        <el-table-column v-if="canWrite" label="操作" width="175"><template #default="{ row }"><el-button link @click="openEditScope(row)">修改</el-button><el-button link @click="toggleStatus('scopes', row)">{{ row.status === 'active' ? '停用' : '启用' }}</el-button><el-button v-if="row.status === 'inactive'" link type="danger" @click="remove('scopes', row)">删除</el-button></template></el-table-column>
      </el-table>
    </div>
  </el-drawer>

  <el-dialog v-model="dialogVisible" :title="`${editingUid ? '修改' : '新增'}${kindNames[editingKind]}`" width="680px" destroy-on-close>
    <el-alert v-if="editingKind === 'scopes'" class="scope-form-alert" :title="`${selectedCanal?.name ?? '当前渠道'}可设置整条管理，也可拆成多个互不重叠的分管段。`" type="info" :closable="false" show-icon />
    <el-form label-position="top" class="master-edit-form">
      <template v-if="editingKind === 'departments' || editingKind === 'offices'">
        <el-form-item v-if="editingKind === 'offices'" label="所属管理处"><el-select v-model="form.parent_department_uid" filterable><el-option v-for="item in activeDepartments" :key="item.stable_uid" :label="item.name" :value="item.stable_uid" /></el-select></el-form-item>
        <div class="two-column-form"><el-form-item label="名称"><el-input v-model="form.name" /></el-form-item><el-form-item label="业务编码"><el-input v-model="form.business_code" /></el-form-item></div>
      </template>
      <template v-else-if="editingKind === 'canals'">
        <div class="two-column-form"><el-form-item label="渠道名称"><el-input v-model="form.name" /></el-form-item><el-form-item label="渠道类型"><el-select v-model="form.canal_level"><el-option v-for="(label, value) in levelNames" :key="value" :label="label" :value="value" /></el-select></el-form-item></div>
        <el-form-item label="上级渠道（干渠或独立渠道可不选）"><el-select v-model="form.parent_canal_uid" clearable filterable><el-option v-for="item in activeCanals.filter((value) => value.stable_uid !== editingUid)" :key="item.stable_uid" :label="item.name" :value="item.stable_uid" /></el-select></el-form-item>
      </template>
      <template v-else>
        <el-form-item label="当前渠道"><el-input :model-value="selectedCanal?.name" disabled /></el-form-item>
        <el-form-item label="负责管理所"><el-select v-model="form.organization_unit_uid" filterable placeholder="选择负责这个区段的管理所"><el-option v-for="item in activeOffices" :key="item.stable_uid" :label="`${item.name} · ${item.parent_name}`" :value="item.stable_uid" /></el-select></el-form-item>
        <el-form-item label="分管方式"><el-radio-group v-model="form.range_mode" class="scope-mode-picker"><el-radio-button value="whole">整条渠道</el-radio-button><el-radio-button value="segment_known">按桩号分段</el-radio-button><el-radio-button value="segment_unknown">边界待确认</el-radio-button></el-radio-group></el-form-item>
        <div v-if="form.range_mode === 'segment_known'" class="two-column-form"><el-form-item label="起始桩号"><el-input v-model="form.start_stake_text" placeholder="例如 CH12+000" /></el-form-item><el-form-item label="终止桩号"><el-input v-model="form.end_stake_text" placeholder="例如 CH18+500" /></el-form-item></div>
        <el-alert v-else-if="form.range_mode === 'segment_unknown'" title="可以先确定负责管理所，待现场或档案核实后再补充起止桩号。" type="warning" :closable="false" show-icon />
      </template>
      <div class="two-column-form"><el-form-item label="显示顺序"><el-input-number v-model="form.sort_order" :min="0" controls-position="right" /></el-form-item></div>
      <el-form-item label="说明（选填）"><el-input v-model="form.description" type="textarea" :rows="3" maxlength="2000" show-word-limit /></el-form-item>
    </el-form>
    <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存并形成新版本</el-button></template>
  </el-dialog>
</template>
