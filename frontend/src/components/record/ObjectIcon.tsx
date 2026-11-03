import { createElement } from "react";
import type { ComponentType, SVGProps } from "react";
import {
  AppsIcon,
  BookIcon,
  BoxIcon,
  BriefcaseIcon,
  BuildingIcon,
  CalendarIcon,
  CardIcon,
  ChartIcon,
  CheckCircleIcon,
  ClipboardIcon,
  CrownIcon,
  DocumentIcon,
  GaugeIcon,
  LayersIcon,
  LedgerIcon,
  LifebuoyIcon,
  MailIcon,
  MegaphoneIcon,
  NoteIcon,
  PaperclipIcon,
  PassportIcon,
  PercentIcon,
  PersonIcon,
  ReceiptIcon,
  SendIcon,
  TargetIcon,
  TasksIcon,
  UsersIcon,
} from "../icons";
import { cx } from "../ui/cx";

type Icon = ComponentType<SVGProps<SVGSVGElement> & { size?: number }>;

const ICONS: Record<string, Icon> = {
  account: BuildingIcon,
  contact: PersonIcon,
  lead: TargetIcon,
  opportunity: CrownIcon,
  product: BoxIcon,
  pricebook: BookIcon,
  quote: DocumentIcon,
  invoice: ReceiptIcon,
  payment: CardIcon,
  tax: PercentIcon,
  line: LayersIcon,
  case: LifebuoyIcon,
  campaign: MegaphoneIcon,
  member: UsersIcon,
  segment: UsersIcon,
  template: MailIcon,
  send: SendIcon,
  consent: CheckCircleIcon,
  task: TasksIcon,
  event: CalendarIcon,
  note: NoteIcon,
  file: PaperclipIcon,
  passport: PassportIcon,
  matter: BriefcaseIcon,
  checklist: ClipboardIcon,
  agreement: DocumentIcon,
  ledger: LedgerIcon,
  sales: CrownIcon,
  service: LifebuoyIcon,
  marketing: MegaphoneIcon,
  billing: ReceiptIcon,
  analytics: ChartIcon,
  dashboard: GaugeIcon,
};

export function iconFor(name: string | undefined): Icon {
  return (name && ICONS[name]) || AppsIcon;
}

/** Coloured square icon badge for an object or app. */
export function ObjectIcon({
  icon,
  color,
  size = 32,
  className,
}: {
  icon?: string;
  color?: string;
  size?: number;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={cx("inline-flex flex-none items-center justify-center rounded-md text-white", className)}
      style={{ width: size, height: size, backgroundColor: color ?? "#64748b" }}
    >
      {createElement(iconFor(icon), { size: Math.round(size * 0.6) })}
    </span>
  );
}
