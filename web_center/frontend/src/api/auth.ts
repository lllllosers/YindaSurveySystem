import { api, setCsrfToken } from "./http";

export type UserRole = "admin" | "manager" | "reviewer" | "viewer";

export interface CurrentUser {
  user_uid: string;
  username: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  permissions: string[];
}

export interface UserRecord {
  user_uid: string;
  username: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export async function login(username: string, password: string): Promise<CurrentUser> {
  const response = await api.post<{ user: CurrentUser; csrf_token: string }>(
    "/auth/login",
    { username, password },
  );
  setCsrfToken(response.data.csrf_token);
  return response.data.user;
}

export async function getMe(): Promise<CurrentUser> {
  const response = await api.get<CurrentUser>("/auth/me");
  return response.data;
}

export async function refreshCsrf(): Promise<void> {
  const response = await api.get<{ csrf_token: string }>("/auth/csrf");
  setCsrfToken(response.data.csrf_token);
}

export async function logout(): Promise<void> {
  await api.post("/auth/logout");
  setCsrfToken(null);
}

export async function listUsers(): Promise<UserRecord[]> {
  const response = await api.get<UserRecord[]>("/users");
  return response.data;
}

export async function createUser(payload: {
  username: string;
  display_name: string;
  password: string;
  role: UserRole;
  is_active: boolean;
}): Promise<UserRecord> {
  const response = await api.post<UserRecord>("/users", payload);
  return response.data;
}

export async function updateUser(
  userUid: string,
  payload: Partial<{
    display_name: string;
    role: UserRole;
    is_active: boolean;
  }>,
): Promise<UserRecord> {
  const response = await api.patch<UserRecord>(`/users/${userUid}`, payload);
  return response.data;
}

export async function resetUserPassword(
  userUid: string,
  newPassword: string,
): Promise<void> {
  await api.post(`/users/${userUid}/reset-password`, {
    new_password: newPassword,
  });
}

export async function revokeUserSessions(userUid: string): Promise<void> {
  await api.post(`/users/${userUid}/revoke-sessions`);
}
