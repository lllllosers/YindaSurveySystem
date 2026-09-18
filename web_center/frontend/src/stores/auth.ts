import { defineStore } from "pinia";
import { computed, ref } from "vue";

import {
  getMe,
  login as apiLogin,
  logout as apiLogout,
  refreshCsrf,
  type CurrentUser,
} from "../api/auth";
import { setCsrfToken } from "../api/http";

export const useAuthStore = defineStore("auth", () => {
  const user = ref<CurrentUser | null>(null);
  const initialized = ref(false);

  const isAuthenticated = computed(() => user.value !== null);
  const isAdmin = computed(() => user.value?.role === "admin");

  function hasPermission(permission: string): boolean {
    const permissions = user.value?.permissions ?? [];
    return permissions.includes("*") || permissions.includes(permission);
  }

  async function bootstrap(): Promise<void> {
    if (initialized.value) return;
    try {
      user.value = await getMe();
      await refreshCsrf();
    } catch {
      user.value = null;
      setCsrfToken(null);
    } finally {
      initialized.value = true;
    }
  }

  async function login(username: string, password: string): Promise<void> {
    user.value = await apiLogin(username, password);
    initialized.value = true;
  }

  async function logout(): Promise<void> {
    try {
      await apiLogout();
    } finally {
      user.value = null;
      initialized.value = true;
      setCsrfToken(null);
    }
  }

  return {
    user,
    initialized,
    isAuthenticated,
    isAdmin,
    hasPermission,
    bootstrap,
    login,
    logout,
  };
});
