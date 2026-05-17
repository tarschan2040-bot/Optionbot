"use client";

import AuthModal from "@/components/AuthModal";

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-gray-950">
      <AuthModal open initialMode="login" onClose={() => window.history.back()} />
    </div>
  );
}
