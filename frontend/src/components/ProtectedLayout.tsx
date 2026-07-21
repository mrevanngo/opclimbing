import { Link, Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../store/auth';

/** Gate for authenticated routes: redirects to /login when there is no user,
 *  otherwise renders the app nav and the matched child route. */
export default function ProtectedLayout() {
  const user = useAuth();
  const location = useLocation();

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return (
    <>
      <nav className="nav">
        <Link className="brand" to="/">
          OptimalClimbing
        </Link>
        <div className="spacer" />
        <Link to="/">Home</Link>
        <Link to="/profile">Profile</Link>
      </nav>
      <Outlet />
    </>
  );
}
