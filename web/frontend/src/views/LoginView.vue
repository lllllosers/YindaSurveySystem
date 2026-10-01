<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";

import { useAuthStore } from "../stores/auth";
import { register } from "../api/auth";
import aqueductHero from "../assets/zhuanglang-aqueduct-hero.png";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const formRef = ref<FormInstance>();
const registerFormRef = ref<FormInstance>();
const submitting = ref(false);
const registering = ref(false);
const registerMode = ref(false);
const registered = ref(false);
const registeredByInvite = ref(false);
const loginVisualStyle = {
  backgroundImage: `linear-gradient(90deg, rgba(4, 18, 43, .88) 0%, rgba(6, 33, 67, .66) 48%, rgba(4, 25, 53, .32) 100%), url(${aqueductHero})`,
};

const form = reactive({
  username: "",
  password: "",
});
const registerForm = reactive({ username: "", display_name: "", password: "", confirmPassword: "", invite_code: "" });

const rules: FormRules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
};
const registerRules: FormRules = {
  username: [
    { required: true, message: "请设置用户名", trigger: "blur" },
    { min: 3, max: 80, message: "用户名长度为 3～80 位", trigger: "blur" },
    { pattern: /^[a-zA-Z0-9_-]+$/, message: "仅支持字母、数字、下划线和短横线", trigger: "blur" },
  ],
  display_name: [{ required: true, message: "请输入姓名", trigger: "blur" }],
  password: [{ required: true, message: "请设置密码", trigger: "blur" }, { min: 8, max: 128, message: "密码长度为 8～128 位", trigger: "blur" }],
  confirmPassword: [{ required: true, message: "请再次输入密码", trigger: "blur" }, { validator: (_rule, value, callback) => value === registerForm.password ? callback() : callback(new Error("两次输入的密码不一致")), trigger: "blur" }],
};

async function submit() {
  if (!(await formRef.value?.validate())) return;

  submitting.value = true;
  try {
    await auth.login(form.username, form.password);
    const redirect =
      typeof route.query.redirect === "string" ? route.query.redirect : "/";
    await router.replace(redirect);
  } catch (error: any) {
    if (error?.response?.status === 429) {
      ElMessage.error("连续登录失败次数过多，请稍后再试");
    } else {
      ElMessage.error("用户名或密码错误");
    }
  } finally {
    submitting.value = false;
  }
}

async function submitRegistration() {
  if (!(await registerFormRef.value?.validate())) return;
  registering.value = true;
  try {
    const result = await register({ username: registerForm.username, display_name: registerForm.display_name, password: registerForm.password, invite_code: registerForm.invite_code.trim() || undefined });
    registered.value = true;
    registeredByInvite.value = result.active;
    ElMessage.success(result.message);
  } catch (error: any) {
    const detail = error?.response?.data?.detail;
    ElMessage.error(error?.response?.status === 409 ? "该用户名已被使用" : typeof detail === "string" ? detail : "注册失败，请检查填写内容后重试");
  } finally {
    registering.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-visual" :style="loginVisualStyle">
      <div class="login-visual-content">
        <div class="visual-kicker">引大入秦 · 调查成果协同管理</div>
        <h1>统一安排每一次调查<br />完整沉淀每一份成果</h1>
        <p>中心统一安排，基层离线调查，成果集中审核归档。</p>
        <div class="visual-flow">
          <span>中心安排任务</span><i></i><span>基层离线调查</span><i></i><span>成果集中归档</span>
        </div>
      </div>
      <div class="water-lines" aria-hidden="true"><span></span><span></span><span></span></div>
    </div>

    <div class="login-side">
      <div class="login-panel">
        <div class="login-brand">
          <div class="brand-mark login-mark"><span>引</span></div>
          <div>
            <div class="login-title">引大调查数据中心</div>
            <div class="login-subtitle">中心业务管理平台</div>
          </div>
        </div>

        <div class="login-heading">{{ registerMode ? "申请账户" : "欢迎回来" }}</div>
        <div class="login-description">{{ registerMode ? "有邀请口令可直接启用；普通申请由管理员批量审核。" : "使用已有账户登录调查数据中心。" }}</div>

        <el-alert v-if="registered" :title="registeredByInvite ? '注册成功' : '注册申请已提交'" :description="registeredByInvite ? '账户已启用，请返回登录。' : '管理员启用账户后即可登录。请联系系统管理员了解审核进度。'" type="success" :closable="false" show-icon />
        <el-form
          v-else-if="registerMode"
          ref="registerFormRef"
          :model="registerForm"
          :rules="registerRules"
          label-position="top"
          @keyup.enter="submitRegistration"
        >
          <el-form-item label="用户名" prop="username"><el-input v-model="registerForm.username" size="large" autocomplete="username" placeholder="3～80 位字母、数字或 _ -" /></el-form-item>
          <el-form-item label="姓名" prop="display_name"><el-input v-model="registerForm.display_name" size="large" autocomplete="name" placeholder="请输入姓名" /></el-form-item>
          <el-form-item label="密码" prop="password"><el-input v-model="registerForm.password" type="password" size="large" show-password autocomplete="new-password" /></el-form-item>
          <el-form-item label="确认密码" prop="confirmPassword"><el-input v-model="registerForm.confirmPassword" type="password" size="large" show-password autocomplete="new-password" /></el-form-item>
          <el-form-item label="邀请口令（选填）"><el-input v-model="registerForm.invite_code" size="large" placeholder="由系统管理员提供" autocomplete="off" /></el-form-item>
          <el-button type="primary" size="large" class="login-button" :loading="registering" @click="submitRegistration">注册账户</el-button>
        </el-form>
        <el-form
          v-else
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          @keyup.enter="submit"
        >
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" size="large" autocomplete="username" placeholder="请输入用户名" />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              size="large"
              show-password
              autocomplete="current-password"
              placeholder="请输入密码"
            />
          </el-form-item>
          <el-button
            type="primary"
            size="large"
            class="login-button"
            :loading="submitting"
            @click="submit"
          >
            进入数据中心
          </el-button>
        </el-form>

        <div class="register-switch">
          <template v-if="registerMode || registered">已有账户？<el-link type="primary" @click="registerMode = false; registered = false">返回登录</el-link></template>
          <template v-else>还没有账户？<el-link type="primary" @click="registerMode = true; registered = false">申请注册</el-link></template>
        </div>

        <div class="login-security-note"><span></span>登录信息和业务数据均已安全保护</div>
      </div>
      <div class="login-footer">引大入秦灌区现状调查 · V1.2.0</div>
    </div>
  </div>
</template>
