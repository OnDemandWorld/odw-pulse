import { Link, useLocation } from 'react-router-dom';
import { ReactNode } from 'react';

interface NavLinkProps {
  to: string;
  children: ReactNode;
  icon?: ReactNode;
}

export default function NavLink({ to, children, icon }: NavLinkProps) {
  const location = useLocation();
  const isActive = location.pathname === to;

  return (
    <Link
      to={to}
      className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
        isActive
          ? 'bg-blue-50 text-blue-700 font-medium'
          : 'text-gray-700 hover:bg-gray-100'
      }`}
    >
      {icon && <span className="text-xl">{icon}</span>}
      <span>{children}</span>
    </Link>
  );
}
