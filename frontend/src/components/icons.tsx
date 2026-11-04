// Inline SVG icons (stroke style). Decorative by default (aria-hidden); pass a label via the parent control.
import type { ReactNode, SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function make(paths: ReactNode) {
  return function Icon({ size = 20, ...rest }: IconProps) {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        focusable="false"
        {...rest}
      >
        {paths}
      </svg>
    );
  };
}

export const HomeIcon = make(
  <>
    <path d="M3 10.5 12 3l9 7.5" />
    <path d="M5 9.5V21h5v-6h4v6h5V9.5" />
  </>,
);
export const ShieldIcon = make(
  <>
    <path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6l-8-3z" />
    <path d="m9 12 2 2 4-4" />
  </>,
);
export const UsersIcon = make(
  <>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20c.6-3.6 3.3-5.5 6.5-5.5s5.9 1.9 6.5 5.5" />
    <path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.8c2 .7 3.2 2.5 3.5 5.2" />
  </>,
);
export const ClipboardIcon = make(
  <>
    <rect x="5" y="4" width="14" height="17" rx="2" />
    <path d="M9 4V3h6v1M9 10h6M9 14h6M9 18h4" />
  </>,
);
export const SearchIcon = make(
  <>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m20 20-4.2-4.2" />
  </>,
);
export const HelpIcon = make(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7M12 17h.01" />
  </>,
);
export const SettingsIcon = make(
  <>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
  </>,
);
export const BellIcon = make(
  <>
    <path d="M6 9a6 6 0 1 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9z" />
    <path d="M10 20a2 2 0 0 0 4 0" />
  </>,
);
export const ChevronDownIcon = make(<path d="m6 9 6 6 6-6" />);
export const MenuIcon = make(<path d="M4 6h16M4 12h16M4 18h16" />);
export const CloseIcon = make(<path d="M6 6l12 12M18 6 6 18" />);
export const RefreshIcon = make(
  <>
    <path d="M20 11a8 8 0 0 0-14.6-4.5L4 8" />
    <path d="M4 4v4h4M4 13a8 8 0 0 0 14.6 4.5L20 16" />
    <path d="M20 20v-4h-4" />
  </>,
);
export const PlusIcon = make(<path d="M12 5v14M5 12h14" />);
export const InboxIcon = make(
  <>
    <path d="M3 13h5l1.5 3h5L16 13h5" />
    <path d="M5 5h14l2 8v6H3v-6l2-8z" />
  </>,
);
export const TasksIcon = make(
  <>
    <rect x="4" y="4" width="16" height="16" rx="3" />
    <path d="m8 12 3 3 5-6" />
  </>,
);
export const ClockIcon = make(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </>,
);
export const PulseIcon = make(<path d="M3 12h4l2-6 4 12 2-6h6" />);
export const AppsIcon = make(
  <>
    <rect x="4" y="4" width="6" height="6" rx="1.5" />
    <rect x="14" y="4" width="6" height="6" rx="1.5" />
    <rect x="4" y="14" width="6" height="6" rx="1.5" />
    <rect x="14" y="14" width="6" height="6" rx="1.5" />
  </>,
);

export const BuildingIcon = make(
  <>
    <path d="M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16" />
    <path d="M15 9h4a1 1 0 0 1 1 1v11" />
    <path d="M3 21h18M8 8h3M8 12h3M8 16h3" />
  </>,
);
export const PersonIcon = make(
  <>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" />
  </>,
);
export const TargetIcon = make(
  <>
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="5" />
    <circle cx="12" cy="12" r="1" />
  </>,
);
export const CrownIcon = make(<path d="m3 8 4.5 4L12 5l4.5 7L21 8l-2 11H5L3 8z" />);
export const BoxIcon = make(
  <>
    <path d="M21 8 12 3 3 8v8l9 5 9-5V8z" />
    <path d="m3 8 9 5 9-5M12 13v8" />
  </>,
);
export const BookIcon = make(
  <>
    <path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5z" />
    <path d="M4 19a2 2 0 0 1 2-2h13" />
  </>,
);
export const DocumentIcon = make(
  <>
    <path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8l-5-5z" />
    <path d="M14 3v5h5M9 13h6M9 17h6" />
  </>,
);
export const ReceiptIcon = make(
  <>
    <path d="M5 3h14v18l-3-2-2 2-2-2-2 2-2-2-3 2V3z" />
    <path d="M9 8h6M9 12h6M9 16h3" />
  </>,
);
export const CardIcon = make(
  <>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M3 10h18M7 15h3" />
  </>,
);
export const PercentIcon = make(
  <>
    <path d="M19 5 5 19" />
    <circle cx="7" cy="7" r="2" />
    <circle cx="17" cy="17" r="2" />
  </>,
);
export const LifebuoyIcon = make(
  <>
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="4" />
    <path d="m5.6 5.6 3.6 3.6M14.8 14.8l3.6 3.6M18.4 5.6l-3.6 3.6M9.2 14.8l-3.6 3.6" />
  </>,
);
export const MegaphoneIcon = make(
  <>
    <path d="M3 11v2a1 1 0 0 0 1 1h2l5 4V6L6 10H4a1 1 0 0 0-1 1z" />
    <path d="M15 8a5 5 0 0 1 0 8M18 5a9 9 0 0 1 0 14" />
  </>,
);
export const MailIcon = make(
  <>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="m3 7 9 6 9-6" />
  </>,
);
export const SendIcon = make(<path d="M21 3 3 10l7 3 3 7 8-17zM10 13l5-5" />);
export const FilterIcon = make(<path d="M3 5h18l-7 8v6l-4 2v-8L3 5z" />);
export const ChartIcon = make(
  <>
    <path d="M3 3v18h18" />
    <path d="M7 15v3M11 11v7M15 7v11M19 12v6" />
  </>,
);
export const GaugeIcon = make(
  <>
    <path d="M4 18a8 8 0 1 1 16 0" />
    <path d="m12 14 4-5" />
  </>,
);
export const CalendarIcon = make(
  <>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M3 10h18M8 3v4M16 3v4" />
  </>,
);
export const NoteIcon = make(
  <>
    <path d="M5 3h10l4 4v14H5V3z" />
    <path d="M15 3v4h4M8 12h8M8 16h5" />
  </>,
);
export const PaperclipIcon = make(
  <path d="m21 11-8.5 8.5a5 5 0 0 1-7-7L14 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 7" />,
);
export const CheckIcon = make(<path d="m5 12 5 5L20 7" />);
export const CheckCircleIcon = make(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="m8 12 3 3 5-6" />
  </>,
);
export const PassportIcon = make(
  <>
    <rect x="5" y="3" width="14" height="18" rx="2" />
    <circle cx="12" cy="10" r="3" />
    <path d="M9 17h6" />
  </>,
);
export const BriefcaseIcon = make(
  <>
    <rect x="3" y="7" width="18" height="13" rx="2" />
    <path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 13h18" />
  </>,
);
export const ScaleIcon = make(
  <>
    <path d="M12 3v18M7 21h10M5 7h14" />
    <path d="m5 7-3 6a3 3 0 0 0 6 0L5 7zM19 7l-3 6a3 3 0 0 0 6 0l-3-6z" />
  </>,
);
export const CalculatorIcon = make(
  <>
    <rect x="5" y="3" width="14" height="18" rx="2" />
    <path d="M8 7h8M8 11h.01M12 11h.01M16 11h.01M8 15h.01M12 15h.01M16 15v3M8 18h4" />
  </>,
);
export const LedgerIcon = make(
  <>
    <path d="M4 4h16v16H4z" />
    <path d="M4 9h16M9 4v16M12 13h5M12 16h5" />
  </>,
);
export const LayersIcon = make(
  <>
    <path d="m12 3 9 5-9 5-9-5 9-5z" />
    <path d="m3 13 9 5 9-5" />
  </>,
);
export const TrashIcon = make(
  <>
    <path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" />
  </>,
);
export const EditIcon = make(
  <>
    <path d="M4 20h4L19 9l-4-4L4 16v4z" />
    <path d="m13 7 4 4" />
  </>,
);
export const DownloadIcon = make(
  <>
    <path d="M12 4v11M7 10l5 5 5-5" />
    <path d="M4 20h16" />
  </>,
);
export const UploadIcon = make(
  <>
    <path d="M12 16V5M7 10l5-5 5 5" />
    <path d="M4 20h16" />
  </>,
);
export const GridIcon = make(
  <>
    <rect x="4" y="4" width="7" height="7" rx="1" />
    <rect x="13" y="4" width="7" height="7" rx="1" />
    <rect x="4" y="13" width="7" height="7" rx="1" />
    <rect x="13" y="13" width="7" height="7" rx="1" />
  </>,
);
export const ColumnsIcon = make(
  <>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M9 4v16M15 4v16" />
  </>,
);
export const ListIcon = make(<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />);
export const PinIcon = make(<path d="M9 4h6l-1 6 4 3H6l4-3-1-6zM12 13v8" />);
export const ExternalIcon = make(
  <>
    <path d="M14 4h6v6M20 4l-9 9" />
    <path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" />
  </>,
);
export const ArrowRightIcon = make(<path d="M5 12h14M13 6l6 6-6 6" />);
export const ChevronRightIcon = make(<path d="m9 6 6 6-6 6" />);
export const ChevronLeftIcon = make(<path d="m15 6-6 6 6 6" />);
export const RecycleIcon = make(
  <>
    <path d="M7 19H4l3-5M17 19h3l-3-5M9 5l3-2 3 2" />
    <path d="M7 14 12 5l5 9M7 19h10" />
  </>,
);
export const KeyIcon = make(
  <>
    <circle cx="8" cy="15" r="4" />
    <path d="m11 12 9-9M17 6l3 3" />
  </>,
);
export const PackageIcon = make(
  <>
    <path d="M21 8 12 3 3 8v8l9 5 9-5V8z" />
    <path d="M7.5 5.5 16.5 10.5" />
  </>,
);
export const LockIcon = make(
  <>
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </>,
);
