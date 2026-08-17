"use client";

import dynamic from "next/dynamic";

const EmployeeSearchDialog = dynamic(
  () => import("@/components/employee-search-dialog").then((mod) => mod.EmployeeSearchDialog),
  {
    ssr: false,
  },
);

type EmployeeSearchDialogLazyProps = {
  apiBaseUrl: string;
};

export function EmployeeSearchDialogLazy({ apiBaseUrl }: EmployeeSearchDialogLazyProps) {
  return <EmployeeSearchDialog apiBaseUrl={apiBaseUrl} />;
}