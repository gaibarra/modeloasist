"use client";

import { FormEvent, useState } from "react";

import { SessionUser, getDefaultRouteForUser } from "@/lib/auth";
import { getHumanApiErrorMessage } from "@/lib/api-error";

type LoginState = {
  email: string;
  password: string;
};

export function LoginForm() {
  const [form, setForm] = useState<LoginState>({ email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(form),
      });
      const payload = (await response.json()) as ({ detail?: unknown } & Partial<SessionUser>);
      if (!response.ok || payload.actor_type == null || typeof payload.must_change_password !== "boolean") {
        throw new Error(getHumanApiErrorMessage(payload, "No fue posible iniciar sesión. Intenta nuevamente."));
      }
      const destination = getDefaultRouteForUser(payload as SessionUser);
      window.location.replace(destination);
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
        <label className="field-label" htmlFor="email">
          Correo institucional
        </label>
        <input
          id="email"
          type="email"
          value={form.email}
          onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
          className="field-input"
          placeholder="nombre@modelo.edu.mx"
          required
        />
      </div>
      <div>
        <label className="field-label" htmlFor="password">
          Contraseña
        </label>
        <input
          id="password"
          type="password"
          value={form.password}
          onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
          className="field-input"
          required
        />
      </div>
      {error ? <p className="alert-error">{error}</p> : null}
      {/* <p className="helper-text">
        Si tu área te asignó una contraseña temporal, podrás cambiarla después de iniciar sesión.
      </p> */}
      <button
        type="submit"
        disabled={loading}
        className="primary-button w-full disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Validando acceso..." : "Entrar"}
      </button>
    </form>
  );
}