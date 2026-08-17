type ApiValidationErrorItem = {
  msg?: string;
  loc?: Array<string | number>;
};

type ApiErrorPayload = {
  detail?: string | ApiValidationErrorItem[] | { message?: string };
  message?: string;
};

function humanizeAuthMessage(message: string) {
  switch (message) {
    case "Credenciales inválidas":
    case "El correo o la contraseña no son correctos.":
      return "El correo o la contraseña son incorrectos. Verifica tus datos e inténtalo nuevamente.";
    case "Sesión no encontrada":
      return "Tu sesión ya no está disponible. Inicia sesión nuevamente.";
    case "La contraseña actual no es correcta":
      return "La contraseña actual es incorrecta. Revísala e inténtalo de nuevo.";
    case "Debes elegir una contraseña diferente":
      return "La nueva contraseña debe ser diferente de la actual.";
    default:
      return message;
  }
}

export function getHumanApiErrorMessage(payload: unknown, fallback: string) {
  if (!payload || typeof payload !== "object") {
    return fallback;
  }

  const typedPayload = payload as ApiErrorPayload;

  if (typeof typedPayload.detail === "string") {
    return humanizeAuthMessage(typedPayload.detail);
  }

  if (Array.isArray(typedPayload.detail) && typedPayload.detail.length > 0) {
    const firstError = typedPayload.detail[0];
    if (typeof firstError?.msg === "string") {
      if (firstError.msg.toLowerCase().includes("valid email")) {
        return "Escribe un correo institucional válido.";
      }
      if (firstError.msg.toLowerCase().includes("at least 8 characters")) {
        return "La contraseña debe tener al menos 8 caracteres.";
      }
      return firstError.msg;
    }
    return fallback;
  }

  if (
    typedPayload.detail &&
    !Array.isArray(typedPayload.detail) &&
    typeof typedPayload.detail === "object" &&
    typeof typedPayload.detail.message === "string"
  ) {
    return humanizeAuthMessage(typedPayload.detail.message);
  }

  if (typeof typedPayload.message === "string") {
    return humanizeAuthMessage(typedPayload.message);
  }

  return fallback;
}