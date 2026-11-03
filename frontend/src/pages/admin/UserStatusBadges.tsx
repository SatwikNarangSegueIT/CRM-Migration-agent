import { isLocked, type User } from "../../api/users";
import { Badge } from "../../components/ui";

export function UserStatusBadges({ user }: { user: User }) {
  return (
    <span className="flex flex-wrap gap-1">
      {!user.is_active ? (
        <Badge tone="gray">Inactive</Badge>
      ) : !user.has_password ? (
        <Badge tone="blue">Invited</Badge>
      ) : (
        <Badge tone="green">Active</Badge>
      )}
      {isLocked(user) && <Badge tone="red">Locked</Badge>}
      {user.mfa_enabled && <Badge tone="purple">MFA</Badge>}
    </span>
  );
}
