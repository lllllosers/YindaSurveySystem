<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
} from "element-plus";

import {
  approveUsers,
  createInvite,
  createUser,
  deleteUser,
  dismissPendingUsers,
  listInvites,
  listUsers,
  resetUserPassword,
  revokeUserSessions,
  revokeInvite,
  updateUser,
  type UserRecord,
  type UserRole,
  type CreatedInvite,
  type RegistrationInvite,
} from "../api/auth";
import { useAuthStore } from "../stores/auth";
import { getMasterDataSnapshot, type Office } from "../api/masterData";

const auth = useAuthStore();
const loading = ref(false);
const users = ref<UserRecord[]>([]);
const offices = ref<Office[]>([]);
const invites = ref<RegistrationInvite[]>([]);
const inviteDialog = ref(false);
const createdInvite = ref<CreatedInvite | null>(null);
const inviteResultVisible = ref(false);
const inviteBusy = ref(false);
const inviteForm = reactive({ label: "", role: "viewer" as Exclude<UserRole, "admin">, max_uses: 20, valid_days: 7, office_scope_uid: null as string | null });
const pendingOnly = ref(false);
const selectedPending = ref<UserRecord[]>([]);
const approvalDialog = ref(false);
const approvalBusy = ref(false);
const dismissBusy = ref(false);
const approvalRole = ref<Exclude<UserRole, "admin">>("viewer");
const approvalOfficeScopeUid = ref<string | null>(null);
const pendingCount = computed(() => users.value.filter((user) => !user.is_approved).length);
const visibleUsers = computed(() => pendingOnly.value ? users.value.filter((user) => !user.is_approved) : users.value);
const createDialog = ref(false);
const editDialog = ref(false);
const createFormRef = ref<FormInstance>();

const createForm = reactive({
  username: "",
  display_name: "",
  password: "",
  role: "viewer" as UserRole,
  is_active: true,
  office_scope_uid: null as string | null,
});

const editForm = reactive({
  user_uid: "",
  username: "",
  display_name: "",
  role: "viewer" as UserRole,
  is_active: true,
  office_scope_uid: null as string | null,
});

const rules: FormRules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  display_name: [{ required: true, message: "请输入显示姓名", trigger: "blur" }],
  password: [
    { required: true, message: "请输入初始密码", trigger: "blur" },
    { min: 6, message: "密码至少 6 个字符", trigger: "blur" },
  ],
};

const roleLabels: Record<UserRole, string> = {
  admin: "系统管理员",
  manager: "管理人员",
  reviewer: "审核人员",
  viewer: "查询人员",
};

function scopeName(uid: string | null): string {
  return uid ? offices.value.find((item) => item.stable_uid === uid)?.name || "已指定管理所" : "全中心";
}

async function refresh() {
  loading.value = true;
  try {
    users.value = await listUsers();
    selectedPending.value = [];
  } finally {
    loading.value = false;
  }
}

async function refreshInvites() {
  try {
    invites.value = await listInvites();
  } catch {
    ElMessage.error("邀请列表加载失败");
  }
}

function inviteState(item: RegistrationInvite): string {
  if (item.revoked_at) return "已停用";
  if (new Date(item.expires_at).getTime() <= Date.now()) return "已到期";
  if (item.used_count >= item.max_uses) return "已用完";
  return "可使用";
}

async function submitInvite() {
  if (!inviteForm.label.trim()) {
    ElMessage.warning("请填写邀请用途或人员范围");
    return;
  }
  inviteBusy.value = true;
  try {
    createdInvite.value = await createInvite({ ...inviteForm, label: inviteForm.label.trim() });
    inviteResultVisible.value = true;
    inviteDialog.value = false;
    inviteForm.label = "";
    await refreshInvites();
    ElMessage.success("邀请口令已生成，请复制后交给受邀人员");
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || "邀请创建失败");
  } finally {
    inviteBusy.value = false;
  }
}

async function copyInvite() {
  if (!createdInvite.value) return;
  try {
    await navigator.clipboard.writeText(createdInvite.value.code);
    ElMessage.success("邀请口令已复制");
  } catch {
    ElMessage.warning("复制失败，请手动选中口令复制");
  }
}

async function disableInvite(item: RegistrationInvite) {
  try {
    await ElMessageBox.confirm(`停用“${item.label}”的邀请口令？已注册账户不会受影响。`, "停用邀请", { type: "warning" });
    await revokeInvite(item.invite_uid);
    ElMessage.success("邀请口令已停用");
    await refreshInvites();
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error?.response?.data?.detail || "停用失败");
  }
}

async function removeUser(user: UserRecord) {
  try {
    await ElMessageBox.confirm(`删除账户“${user.username}”？有业务记录的账户只能停用，以保留责任历史。`, "删除账户", { type: "warning", confirmButtonText: "删除" });
    await deleteUser(user.user_uid);
    ElMessage.success("账户已删除");
    await refresh();
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error?.response?.data?.detail || "账户删除失败");
  }
}

function openCreate() {
  createForm.username = "";
  createForm.display_name = "";
  createForm.password = "";
  createForm.role = "viewer";
  createForm.is_active = true;
  createForm.office_scope_uid = null;
  createDialog.value = true;
}

function openEdit(user: UserRecord) {
  editForm.user_uid = user.user_uid;
  editForm.username = user.username;
  editForm.display_name = user.display_name;
  editForm.role = user.role;
  editForm.is_active = user.is_active;
  editForm.office_scope_uid = user.office_scope_uid;
  editDialog.value = true;
}

async function saveCreate() {
  if (!(await createFormRef.value?.validate())) return;
  try {
    await createUser({ ...createForm });
    createDialog.value = false;
    ElMessage.success("用户已创建");
    await refresh();
  } catch (error: any) {
    ElMessage.error(
      error?.response?.status === 409 ? "用户名已存在" : "用户创建失败",
    );
  }
}

async function saveEdit() {
  try {
    await updateUser(editForm.user_uid, {
      display_name: editForm.display_name,
      role: editForm.role,
      is_active: editForm.is_active,
      office_scope_uid: editForm.office_scope_uid,
    });
    editDialog.value = false;
    ElMessage.success("用户已更新");
    await refresh();
  } catch {
    ElMessage.error("用户信息保存失败，请稍后重试");
  }
}

async function approveUser(user: UserRecord) {
  selectedPending.value = [user];
  openBatchApproval();
}

function openBatchApproval() {
  if (!selectedPending.value.length) {
    ElMessage.warning("请先勾选待审核账户");
    return;
  }
  if (selectedPending.value.length > 200) {
    ElMessage.warning("每次最多审核 200 个申请，请分批选择");
    return;
  }
  approvalRole.value = "viewer";
  approvalOfficeScopeUid.value = null;
  approvalDialog.value = true;
}

async function dismissSelected() {
  const count = selectedPending.value.length;
  if (!count) return;
  if (count > 200) {
    ElMessage.warning("每次最多清理 200 个申请，请分批选择");
    return;
  }
  try {
    await ElMessageBox.confirm(
      `将清理选中的 ${count} 个待审核申请。这些账户尚未启用，清理后申请人可重新注册。确认继续？`,
      "清理无效申请",
      { type: "warning", confirmButtonText: "确认清理" },
    );
    dismissBusy.value = true;
    await dismissPendingUsers(selectedPending.value.map((user) => user.user_uid));
    ElMessage.success(`已清理 ${count} 个待审核申请`);
    await refresh();
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") {
      ElMessage.error(error?.response?.data?.detail || "清理失败，请刷新后重试");
    }
  } finally {
    dismissBusy.value = false;
  }
}

async function submitBatchApproval() {
  approvalBusy.value = true;
  try {
    const count = selectedPending.value.length;
    await approveUsers(selectedPending.value.map((user) => user.user_uid), approvalRole.value, approvalRole.value === "manager" ? null : approvalOfficeScopeUid.value);
    approvalDialog.value = false;
    ElMessage.success(`已启用 ${count} 个账户`);
    await refresh();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || "批量审核失败，请刷新后重试");
  } finally {
    approvalBusy.value = false;
  }
}

async function resetPassword(user: UserRecord) {
  try {
    const result = await ElMessageBox.prompt(
      `为“${user.display_name}”设置新密码（至少 6 个字符）。重置后该用户需要在所有设备上重新登录。`,
      "重置密码",
      {
        confirmButtonText: "重置",
        cancelButtonText: "取消",
        inputType: "password",
        inputPattern: /^.{6,128}$/,
        inputErrorMessage: "密码长度必须为 6～128 个字符",
      },
    );
    await resetUserPassword(user.user_uid, result.value);
    ElMessage.success("密码已重置，该用户需要重新登录");
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error("密码重置失败");
  }
}

async function revokeSessions(user: UserRecord) {
  try {
    await ElMessageBox.confirm(
      `确认让“${user.display_name}”在所有设备上退出登录？`,
      "强制退出登录",
      {
        confirmButtonText: "确认退出",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
    await revokeUserSessions(user.user_uid);
    ElMessage.success("该用户已在所有设备上退出登录");
    if (user.user_uid === auth.user?.user_uid) {
      window.location.assign("/login");
    }
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error("强制退出失败，请稍后重试");
  }
}

function formatTime(value: string | null) {
  if (!value) return "从未登录";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

onMounted(() => {
  void refresh();
  void refreshInvites();
  void getMasterDataSnapshot().then((snapshot) => { offices.value = snapshot.offices; }).catch(() => ElMessage.error("管理所资料加载失败"));
});
</script>

<template>
  <div class="module-header">
    <div>
      <div class="eyebrow">人员与职责</div>
      <h1>用户与权限</h1>
      <p>为中心管理、任务安排、成果审核和成果查询人员分配合适权限。</p>
    </div>
    <div class="header-actions"><el-button @click="inviteDialog = true">发放注册邀请</el-button><el-button type="primary" @click="openCreate">新建用户</el-button></div>
  </div>

  <el-card shadow="never" class="business-card">
    <div class="user-batch-toolbar">
      <div><el-switch v-model="pendingOnly" active-text="只看待审核" /><el-tag type="warning" effect="plain">{{ pendingCount }} 项待审核</el-tag></div>
      <div>
        <el-button :disabled="!selectedPending.length" :loading="dismissBusy" @click="dismissSelected">清理无效申请</el-button>
        <el-button type="primary" :disabled="!selectedPending.length" @click="openBatchApproval">批量审核（{{ selectedPending.length }}）</el-button>
      </div>
    </div>
    <el-table v-loading="loading" :data="visibleUsers" @selection-change="(rows: UserRecord[]) => selectedPending = rows.filter((row) => !row.is_approved)">
      <el-table-column type="selection" width="50" :selectable="(row: UserRecord) => !row.is_approved" />
      <el-table-column prop="username" label="用户名" width="170" />
      <el-table-column prop="display_name" label="姓名" min-width="160" />
      <el-table-column label="数据范围" min-width="145"><template #default="{ row }">{{ scopeName(row.office_scope_uid) }}</template></el-table-column>
      <el-table-column label="角色" width="135">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">
            {{ roleLabels[row.role as UserRole] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">
            {{ !row.is_approved ? "待审核" : row.is_active ? "启用" : "停用" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最近登录" width="190">
        <template #default="{ row }">{{ formatTime(row.last_login_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button v-if="!row.is_approved" link type="success" @click="approveUser(row)">审核通过</el-button>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link @click="resetPassword(row)">重置密码</el-button>
          <el-button link type="warning" @click="revokeSessions(row)">强制退出</el-button>
          <el-button v-if="row.user_uid !== auth.user?.user_uid" link type="danger" @click="removeUser(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-card shadow="never" class="business-card">
    <template #header><div class="card-header"><span>注册邀请</span><el-button link @click="refreshInvites">刷新</el-button></div></template>
    <p class="batch-approval-note">管理员生成一次口令，可供指定人数在有效期内注册并按预设角色直接启用。口令只在创建时完整显示。</p>
    <el-table :data="invites" stripe>
      <el-table-column prop="label" label="用途或人员范围" min-width="190" />
      <el-table-column label="角色" width="115"><template #default="{ row }">{{ roleLabels[row.role as UserRole] }}</template></el-table-column>
      <el-table-column label="数据范围" min-width="145"><template #default="{ row }">{{ scopeName(row.office_scope_uid) }}</template></el-table-column>
      <el-table-column label="已使用 / 上限" width="130"><template #default="{ row }">{{ row.used_count }} / {{ row.max_uses }}</template></el-table-column>
      <el-table-column label="到期时间" width="185"><template #default="{ row }">{{ formatTime(row.expires_at) }}</template></el-table-column>
      <el-table-column label="状态" width="105"><template #default="{ row }"><el-tag :type="inviteState(row) === '可使用' ? 'success' : 'info'">{{ inviteState(row) }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="105"><template #default="{ row }"><el-button v-if="inviteState(row) === '可使用'" link type="warning" @click="disableInvite(row)">停用</el-button><span v-else>—</span></template></el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="inviteDialog" title="发放注册邀请" width="520px">
    <el-alert title="请通过可信渠道交付口令；口令泄露时可立即停用。" type="warning" :closable="false" show-icon />
    <el-form :model="inviteForm" label-position="top" style="margin-top: 16px">
      <el-form-item label="用途或人员范围"><el-input v-model="inviteForm.label" maxlength="120" placeholder="例如：某管理所本周新员工" /></el-form-item>
      <el-form-item label="注册后角色"><el-select v-model="inviteForm.role" style="width: 100%"><el-option label="查询人员" value="viewer" /><el-option label="审核人员" value="reviewer" /><el-option label="管理人员" value="manager" /></el-select></el-form-item>
      <el-form-item v-if="inviteForm.role !== 'manager'" label="可查看的数据范围"><el-select v-model="inviteForm.office_scope_uid" clearable placeholder="全中心" style="width: 100%"><el-option v-for="office in offices" :key="office.stable_uid" :label="`${office.parent_name} · ${office.name}`" :value="office.stable_uid" /></el-select></el-form-item>
      <el-form-item label="最多可注册人数"><el-input-number v-model="inviteForm.max_uses" :min="1" :max="200" /></el-form-item>
      <el-form-item label="有效天数"><el-input-number v-model="inviteForm.valid_days" :min="1" :max="30" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="inviteDialog = false">取消</el-button><el-button type="primary" :loading="inviteBusy" @click="submitInvite">生成口令</el-button></template>
  </el-dialog>

  <el-dialog v-model="inviteResultVisible" title="请保存并交付邀请口令" width="580px" :close-on-click-modal="false" @closed="createdInvite = null">
    <p>口令仅在这里显示一次。受邀人员在登录页选择“申请注册”，填写口令后即可按预设角色登录。</p>
    <el-input :model-value="createdInvite?.code || ''" readonly /><el-button style="margin-top: 12px" type="primary" @click="copyInvite">复制口令</el-button>
    <template #footer><el-button @click="inviteResultVisible = false">我已保存</el-button></template>
  </el-dialog>

  <el-dialog v-model="approvalDialog" title="批量启用注册账户" width="520px">
    <p>已选择 {{ selectedPending.length }} 名申请人。请为这一批账户指定相同的工作角色，启用后即可登录。</p>
    <el-select v-model="approvalRole" style="width: 100%" aria-label="批量指定角色">
      <el-option label="查询人员（只读）" value="viewer" />
      <el-option label="审核人员" value="reviewer" />
      <el-option label="管理人员" value="manager" />
    </el-select>
    <el-select v-if="approvalRole !== 'manager'" v-model="approvalOfficeScopeUid" clearable placeholder="全中心数据范围" style="width: 100%; margin-top: 12px" aria-label="指定管理所数据范围">
      <el-option v-for="office in offices" :key="office.stable_uid" :label="`${office.parent_name} · ${office.name}`" :value="office.stable_uid" />
    </el-select>
    <p class="batch-approval-note">系统管理员账户需要逐人设置，不能批量授予。</p>
    <template #footer>
      <el-button @click="approvalDialog = false">取消</el-button>
      <el-button type="primary" :loading="approvalBusy" @click="submitBatchApproval">确认启用</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="createDialog" title="新建用户" width="520px">
    <el-form ref="createFormRef" :model="createForm" :rules="rules" label-width="90px">
      <el-form-item label="用户名" prop="username">
        <el-input v-model="createForm.username" />
      </el-form-item>
      <el-form-item label="姓名" prop="display_name">
        <el-input v-model="createForm.display_name" />
      </el-form-item>
      <el-form-item label="初始密码" prop="password">
        <el-input v-model="createForm.password" type="password" show-password />
      </el-form-item>
      <el-form-item label="角色">
        <el-select v-model="createForm.role" style="width: 100%">
          <el-option label="系统管理员" value="admin" />
          <el-option label="管理人员" value="manager" />
          <el-option label="审核人员" value="reviewer" />
          <el-option label="查询人员" value="viewer" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="['viewer', 'reviewer'].includes(createForm.role)" label="数据范围"><el-select v-model="createForm.office_scope_uid" clearable placeholder="全中心" style="width: 100%"><el-option v-for="office in offices" :key="office.stable_uid" :label="`${office.parent_name} · ${office.name}`" :value="office.stable_uid" /></el-select></el-form-item>
      <el-form-item label="状态">
        <el-switch v-model="createForm.is_active" active-text="启用" inactive-text="停用" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createDialog = false">取消</el-button>
      <el-button type="primary" @click="saveCreate">创建</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="editDialog" title="编辑用户" width="520px">
    <el-form :model="editForm" label-width="90px">
      <el-form-item label="用户名">
        <el-input :model-value="editForm.username" disabled />
      </el-form-item>
      <el-form-item label="姓名">
        <el-input v-model="editForm.display_name" />
      </el-form-item>
      <el-form-item label="角色">
        <el-select v-model="editForm.role" style="width: 100%">
          <el-option label="系统管理员" value="admin" />
          <el-option label="管理人员" value="manager" />
          <el-option label="审核人员" value="reviewer" />
          <el-option label="查询人员" value="viewer" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="['viewer', 'reviewer'].includes(editForm.role)" label="数据范围"><el-select v-model="editForm.office_scope_uid" clearable placeholder="全中心" style="width: 100%"><el-option v-for="office in offices" :key="office.stable_uid" :label="`${office.parent_name} · ${office.name}`" :value="office.stable_uid" /></el-select></el-form-item>
      <el-form-item label="状态">
        <el-switch v-model="editForm.is_active" active-text="启用" inactive-text="停用" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="editDialog = false">取消</el-button>
      <el-button type="primary" @click="saveEdit">保存</el-button>
    </template>
  </el-dialog>
</template>
