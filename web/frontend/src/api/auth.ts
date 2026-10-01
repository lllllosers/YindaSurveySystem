import { api } from "./http";

export type UserRole =
  | "admin"
  | "manager"
  | "reviewer"
  | "viewer";

export interface CurrentUser {
  user_uid: string;
  username: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  office_scope_uid: string | null;
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
  is_approved: boolean;
  office_scope_uid: string | null;
  last_login_at: string | null;
  created_at: string;
}

export interface RegistrationInvite {
  invite_uid: string;
  code_prefix: string;
  label: string;
  role: Exclude<UserRole, "admin">;
  office_scope_uid: string | null;
  max_uses: number;
  used_count: number;
  expires_at: string;
  revoked_at: string | null;
  created_by_username: string;
  created_at: string;
}

export interface CreatedInvite extends RegistrationInvite {
  code: string;
}

export async function login(
  username: string,
  password: string,
): Promise<CurrentUser> {
  const response = await api.post<{
    user: CurrentUser;
    csrf_token: string;
  }>(
    "/auth/login",
    {
      username,
      password,
    },
  );

  return response.data.user;
}

export async function register(payload: {
  username: string;
  display_name: string;
  password: string;
  invite_code?: string;
}): Promise<{ active: boolean; message: string }> {
  return (await api.post<{ active: boolean; message: string }>("/auth/register", payload)).data;
}

export async function listInvites(): Promise<RegistrationInvite[]> {
  return (await api.get<RegistrationInvite[]>("/users/invites")).data;
}

export async function createInvite(payload: {
  label: string;
  role: Exclude<UserRole, "admin">;
  max_uses: number;
  valid_days: number;
  office_scope_uid: string | null;
}): Promise<CreatedInvite> {
  return (await api.post<CreatedInvite>("/users/invites", payload)).data;
}

export async function revokeInvite(inviteUid: string): Promise<RegistrationInvite> {
  return (await api.post<RegistrationInvite>(`/users/invites/${inviteUid}/revoke`)).data;
}

export async function getMe(): Promise<CurrentUser> {
  const response = await api.get<CurrentUser>(
    "/auth/me",
  );
  return response.data;
}

export async function refreshCsrf(): Promise<void> {
  await api.get(
    "/auth/csrf",
  );
}

export async function logout(): Promise<void> {
  await api.post(
    "/auth/logout",
  );
}

export async function listUsers(): Promise<UserRecord[]> {
  const response = await api.get<UserRecord[]>(
    "/users",
  );
  return response.data;
}

export async function createUser(
  payload: {
    username: string;
    display_name: string;
    password: string;
    role: UserRole;
    is_active: boolean;
    office_scope_uid: string | null;
  },
): Promise<UserRecord> {
  const response = await api.post<UserRecord>(
    "/users",
    payload,
  );
  return response.data;
}

export async function approveUsers(
  userUids: string[],
  role: Exclude<UserRole, "admin">,
  officeScopeUid: string | null = null,
): Promise<UserRecord[]> {
  const response = await api.post<UserRecord[]>("/users/batch-approve", {
    user_uids: userUids,
    role,
    office_scope_uid: officeScopeUid,
  });
  return response.data;
}

export async function dismissPendingUsers(userUids: string[]): Promise<number> {
  const response = await api.post<{ dismissed: number }>("/users/batch-dismiss", {
    user_uids: userUids,
  });
  return response.data.dismissed;
}

export async function updateUser(
  userUid: string,
  payload: Partial<{
    display_name: string;
    role: UserRole;
    is_active: boolean;
    office_scope_uid: string | null;
  }>,
): Promise<UserRecord> {
  const response = await api.patch<UserRecord>(
    `/users/${userUid}`,
    payload,
  );
  return response.data;
}

export async function deleteUser(userUid: string): Promise<void> {
  await api.delete(`/users/${userUid}`);
}

export async function resetUserPassword(
  userUid: string,
  newPassword: string,
): Promise<void> {
  await api.post(
    `/users/${userUid}/reset-password`,
    {
      new_password: newPassword,
    },
  );
}

export async function revokeUserSessions(
  userUid: string,
): Promise<void> {
  await api.post(
    `/users/${userUid}/revoke-sessions`,
  );
}
