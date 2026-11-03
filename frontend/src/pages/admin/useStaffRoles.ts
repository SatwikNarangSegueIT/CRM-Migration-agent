import { useQuery } from "@tanstack/react-query";
import { metaApi } from "../../api/meta";

/** Staff roles (value + label) from /meta/roles; CLIENT accounts are created via portal invitations. */
export function useStaffRoles() {
  return useQuery({
    queryKey: ["meta", "roles"],
    queryFn: ({ signal }) => metaApi.roles(signal),
    staleTime: Infinity,
    select: (roles) => roles.filter((r) => r.is_staff),
  });
}
