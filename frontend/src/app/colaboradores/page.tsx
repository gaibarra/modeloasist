import Link from "next/link";
import { redirect } from "next/navigation";
import { requireAuthenticatedUser } from "@/lib/server-session";
import { getDefaultRouteForUser } from "@/lib/auth";
import { InstitutionHeader } from "@/components/institution-header";
import { CollaboratorManager } from "@/components/collaborator-manager";
export default async function Page() {
  const user = await requireAuthenticatedUser();
  if (user.email.trim().toLowerCase() !== "gaibarra@hotmail.com") redirect(getDefaultRouteForUser(user));
  return <main className="page-shell"><div className="page-container"><InstitutionHeader eyebrow="Administración · Directorio" title="Colaboradores" description="Las personas que hacen Escuela Modelo. Administra sus datos y asignaciones desde un solo lugar." actions={<Link className="secondary-button" href={getDefaultRouteForUser(user)}>Volver al panel</Link>} /><CollaboratorManager /></div></main>;
}
