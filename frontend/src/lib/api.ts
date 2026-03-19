import type { CropProfileRead, RankFieldsResponse } from "../types/ranking";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ??
  "http://localhost:8000/api/v1";

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const data = (await response.json()) as { detail?: string };
      if (data.detail) {
        message = data.detail;
      }
    } catch {
      // Keep the default message when no structured error payload exists.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

export async function fetchCrops(): Promise<CropProfileRead[]> {
  return apiFetch<CropProfileRead[]>("/crops/");
}

export async function rankFieldsForCrop(cropId: number): Promise<RankFieldsResponse> {
  return apiFetch<RankFieldsResponse>("/rank-fields/", {
    method: "POST",
    body: JSON.stringify({
      crop_id: cropId,
      top_n: 5,
    }),
  });
}
