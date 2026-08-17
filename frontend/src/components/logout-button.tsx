"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

export function LogoutButton() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  const handleLogout = async () => {
    setSubmitting(true);
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  };

  return (
    <button
      type="button"
      onClick={handleLogout}
      disabled={submitting}
      className="secondary-button"
    >
      <LogOut className="h-4 w-4" />
      {submitting ? "Saliendo..." : "Cerrar sesión"}
    </button>
  );
}