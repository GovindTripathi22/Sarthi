import React from "react";

export const metadata = {
  title: "AutoPatch — AI-Powered Self-Healing API & Integration Middleware",
  description:
    "Observe API traffic, detect schema drift, validate patches in an isolated sandbox, and gate GitHub PRs with RBAC.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body style={{ margin: 0, padding: 0, backgroundColor: "#060911", color: "#f8fafc" }}>
        {children}
      </body>
    </html>
  );
}
