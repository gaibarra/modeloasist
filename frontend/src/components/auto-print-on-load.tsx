"use client";

import { useEffect } from "react";

export function AutoPrintOnLoad() {
  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      window.print();
    }, 150);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, []);

  return null;
}

export function PrintNowButton() {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="primary-button px-4 py-2 text-sm"
    >
      Imprimir ahora
    </button>
  );
}
