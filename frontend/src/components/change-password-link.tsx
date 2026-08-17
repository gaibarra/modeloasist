import Link from "next/link";
import { KeyRound } from "lucide-react";

type ChangePasswordLinkProps = {
  className?: string;
};

export function ChangePasswordLink({ className = "security-button" }: ChangePasswordLinkProps) {
  return (
    <Link href="/cambiar-password" className={className}>
      <KeyRound className="h-4 w-4" />
      Cambiar contraseña
    </Link>
  );
}