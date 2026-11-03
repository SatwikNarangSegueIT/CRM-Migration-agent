import { useQuery } from "@tanstack/react-query";
import { setupApi } from "../../api/setup";

export type Option = { value: string; label: string };

/** Staff profiles (portal users are invited from a contact instead). */
export function useStaffProfiles() {
  return useQuery({
    queryKey: ["setup", "profiles"],
    queryFn: ({ signal }) => setupApi.profiles(signal),
    staleTime: 60_000,
    select: (profiles): Option[] =>
      profiles.filter((p) => !p.is_portal).map((p) => ({ value: p.id, label: p.name })),
  });
}

/** Role hierarchy, indented by depth, for "who sees whose records". */
export function useHierarchyRoles() {
  return useQuery({
    queryKey: ["setup", "roles"],
    queryFn: ({ signal }) => setupApi.roles(signal),
    staleTime: 60_000,
    select: (roles): Option[] => {
      const byParent = new Map<string | null, typeof roles>();
      for (const r of roles) byParent.set(r.parent_id, [...(byParent.get(r.parent_id) ?? []), r]);
      const out: Option[] = [];
      const walk = (parent: string | null, depth: number) => {
        for (const r of (byParent.get(parent) ?? []).sort((a, b) => a.name.localeCompare(b.name))) {
          out.push({ value: r.id, label: `${"  ".repeat(depth)}${r.name}` });
          walk(r.id, depth + 1);
        }
      };
      walk(null, 0);
      return out;
    },
  });
}
