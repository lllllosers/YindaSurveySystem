<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
} from "element-plus";

import {
  createUser,
  listUsers,
  resetUserPassword,
  revokeUserSessions,
  updateUser,
  type UserRecord,
  type UserRole,
} from "../api/auth";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const loading = ref(false);
const users = ref<UserRecord[]>([]);
const createDialog = ref(false);
const editDialog = ref(false);
const createFormRef = ref<FormInstance>();

const createForm = reactive({
  username: "",
  display_name: "",
  password: "",
  role: "viewer" as UserRole,
  is_active: true,
});

const editForm = reactive({
  user_uid: "",
  username: "",
  display_name: "",
  role: "viewer" as UserRole,
  is_active: true,
});

const rules: FormRules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  display_name: [{ required: true, message: "请输入显示姓名", trigger: "blur" }],
  password: [
    { required: true, message: "请输入初始密码", trigger: "blur" },
    { min: 10, message: "密码至少 10 个字符", trigger: "blur" },
  ],
};

const roleLabels: Record<UserRole, string> = {
  admin: "系统管理员",
  manager: "管理人员",
  reviewer: "审核人员",
  viewer: "只读人员",
};

async function refresh() {
  loading.value = true;
  try {
    users.value = await listUsers();
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  createForm.username = "";
  createForm.display_name = "";
  createForm.password = "";
  createForm.role = "viewer";
  createForm.is_active = true;
  createDialog.value = true;
}

function openEdit(user: UserRecord) {
  editForm.user_uid = user.user_uid;
  editForm.username = user.username;
  editForm.display_name = user.display_name;
  editForm.role = user.role;
  editForm.is_active = user.is_active;
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
    });
    editDialog.value = false;
    ElMessage.success("用户已更新");
    await refresh();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? "用户更新失败");
  }
}

async function resetPassword(user: UserRecord) {
  try {
    const result = await ElMessageBox.prompt(
      `为“${user.display_name}”设置新密码（至少 10 个字符）。重置后该用户所有会话都会失效。`,
      "重置密码",
      {
        confirmButtonText: "重置",
        cancelButtonText: "取消",
        inputType: "password",
        inputPattern: /^.{10,128}$/,
        inputErrorMessage: "密码长度必须为 10～128 个字符",
      },
    );
    await resetUserPassword(user.user_uid, result.value);
    ElMessage.success("密码已重置，原有会话已撤销");
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error("密码重置失败");
  }
}

async function revokeSessions(user: UserRecord) {
  try {
    await ElMessageBox.confirm(
      `确认撤销“${user.display_name}”的全部登录会话？`,
      "撤销登录会话",
      {
        confirmButtonText: "撤销",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
    await revokeUserSessions(user.user_uid);
    ElMessage.success("该用户的全部登录会话已撤销");
    if (user.user_uid === auth.user?.user_uid) {
      window.location.assign("/login");
    }
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error("会话撤销失败");
  }
}

function formatTime(value: string | null) {
  if (!value) return "从未登录";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

onMounted(refresh);
</script>

<template>
  <div class="module-header">
    <div>
      <h1>用户与权限</h1>
      <p>用户名唯一且不可修改；停用账户不删除历史身份。权限由角色统一控制。</p>
    </div>
    <el-button type="primary" @click="openCreate">新建用户</el-button>
  </div>

  <el-card shadow="never" class="business-card">
    <el-table v-loading="loading" :data="users">
      <el-table-column prop="username" label="用户名" width="170" />
      <el-table-column prop="display_name" label="姓名" min-width="160" />
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
            {{ row.is_active ? "启用" : "停用" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最近登录" width="190">
        <template #default="{ row }">{{ formatTime(row.last_login_at) }}</template>
      </el-table-column>
      <el-table-column label="稳定 UID" min-width="285">
        <template #default="{ row }"><span class="mono">{{ row.user_uid }}</span></template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link @click="resetPassword(row)">重置密码</el-button>
          <el-button link type="warning" @click="revokeSessions(row)">撤销会话</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

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
          <el-option label="只读人员" value="viewer" />
        </el-select>
      </el-form-item>
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
          <el-option label="只读人员" value="viewer" />
        </el-select>
      </el-form-item>
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
