"use client";

import { FormEvent, useState } from "react";

import { AuthSubjectResponse, getDefaultRouteForUser, resolveSessionUser } from "@/lib/auth";
import { getHumanApiErrorMessage } from "@/lib/api-error";

type PasswordState = {
  current_password: string;
  new_password: string;
  confirm_password: string;
};

export function ChangePasswordForm() {
  const [form, setForm] = useState<PasswordState>({
    current_password: "",
    new_password: "",
    confirm_password: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (form.new_password !== form.confirm_password) {
      setError("La confirmación no coincide con la nueva contraseña");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch("/api/auth/change-password", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          current_password: form.current_password,
          new_password: form.new_password,
        }),
      });
      const payload = (await response.json()) as ({ detail?: unknown } & Partial<AuthSubjectResponse>);
      if (!response.ok) {
        throw new Error(getHumanApiErrorMessage(payload, "No fue posible actualizar la contraseña."));
      }
      window.location.replace(getDefaultRouteForUser(resolveSessionUser(payload as AuthSubjectResponse)));
      return;
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <label className="field-label" htmlFor="current_password">
          Contraseña actual
        </label>
        <input
          id="current_password"
          type="password"
          value={form.current_password}
          onChange={(event) => setForm((current) => ({ ...current, current_password: event.target.value }))}
          className="field-input"
          required
        />
      </div>
      <div>
        <label className="field-label" htmlFor="new_password">
          Nueva contraseña
        </label>
        <input
          id="new_password"
          type="password"
          value={form.new_password}
          onChange={(event) => setForm((current) => ({ ...current, new_password: event.target.value }))}
          className="field-input"
          minLength={8}
          required
        />
      </div>
      <div>
        <label className="field-label" htmlFor="confirm_password">
          Confirmar contraseña
        </label>
        <input
          id="confirm_password"
          type="password"
          value={form.confirm_password}
          onChange={(event) => setForm((current) => ({ ...current, confirm_password: event.target.value }))}
          className="field-input"
          minLength={8}
          required
        />
      </div>
      {error ? <p className="alert-error">{error}</p> : null}
      <button
        type="submit"
        disabled={loading}
        className="primary-button w-full disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Actualizando..." : "Guardar nueva contraseña"}
      </button>
    </form>
  );
}