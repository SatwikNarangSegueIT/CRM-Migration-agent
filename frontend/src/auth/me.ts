import { authApi, type MeResponse } from "../api/auth";
import { ApiError } from "../api/client";

/** GET /auth/me; a 401 means "not signed in" and resolves to null rather than an error. */
export async function fetchMe(signal?: AbortSignal): Promise<MeResponse | null> {
  try {
    return await authApi.me(signal);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}
