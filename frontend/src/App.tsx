import { Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";

import { canAccess, useAuth } from "./auth";
import { Layout, PageHeader } from "./components/Layout";
import { Empty, Spinner } from "./components/ui";
import { AdminDashboard } from "./pages/AdminDashboard";
import { CapacityPlan } from "./pages/CapacityPlan";
import { Interview } from "./pages/Interview";
import { Learning } from "./pages/Learning";
import { LearnerDashboard } from "./pages/LearnerDashboard";
import { Login } from "./pages/Login";
import { Promotion } from "./pages/Promotion";
import { Quiz } from "./pages/Quiz";
import { Settings } from "./pages/Settings";
import { ReviewQueue } from "./pages/ReviewQueue";
import { TeamDashboard } from "./pages/TeamDashboard";
import { usePageTitle } from "./hooks/usePageTitle";
import { useT } from "./i18n";

function NoAccess() {
  const t = useT();
  usePageTitle("title.noAccess");
  return (
    <>
      <PageHeader
        title={t("common.noAccessTitle")}
        subtitle={t("common.noAccessSubtitle")}
      />
      <Empty>{t("common.noAccessBody")}</Empty>
    </>
  );
}

/** Route guard. The API enforces RBAC independently — this only avoids showing
 *  someone a screen that would come back 403. */
function Protected({ path, children }: { path: string; children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner label="Checking your session" />;
  if (!user) return <Navigate to="/login" replace />;
  if (!canAccess(user.role, path)) {
    // A denied screen is still a page: it needs a heading to land focus on and
    // a title, or a screen reader is told nothing happened.
    return (
      <Layout>
        <NoAccess />
      </Layout>
    );
  }
  return <Layout>{children}</Layout>;
}

export function App() {
  const { user, loading } = useAuth();

  return (
    <Routes>
      <Route
        path="/login"
        element={loading ? <Spinner /> : user ? <Navigate to="/" replace /> : <Login />}
      />
      <Route
        path="/"
        element={
          <Protected path="/">
            <LearnerDashboard />
          </Protected>
        }
      />
      <Route
        path="/team"
        element={
          <Protected path="/team">
            <TeamDashboard />
          </Protected>
        }
      />
      <Route
        path="/review"
        element={
          <Protected path="/review">
            <ReviewQueue />
          </Protected>
        }
      />
      <Route
        path="/admin"
        element={
          <Protected path="/admin">
            <AdminDashboard />
          </Protected>
        }
      />
      <Route
        path="/acbp"
        element={
          <Protected path="/acbp">
            <CapacityPlan />
          </Protected>
        }
      />
      <Route
        path="/learning"
        element={
          <Protected path="/learning">
            <Learning />
          </Protected>
        }
      />
      <Route
        path="/promotion"
        element={
          <Protected path="/promotion">
            <Promotion />
          </Protected>
        }
      />
      <Route
        path="/quiz"
        element={
          <Protected path="/quiz">
            <Quiz />
          </Protected>
        }
      />
      <Route
        path="/interview"
        element={
          <Protected path="/interview">
            <Interview />
          </Protected>
        }
      />
      <Route
        path="/settings"
        element={
          <Protected path="/settings">
            <Settings />
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
