// Set when the user signs out on purpose, so guards send them to /login without a "next" return path
// (otherwise the next person signing in on this browser would land on the previous user's page).
let explicitSignOut = false;

export function markSignedOut(value: boolean): void {
  explicitSignOut = value;
}

export function wasSignedOut(): boolean {
  return explicitSignOut;
}
