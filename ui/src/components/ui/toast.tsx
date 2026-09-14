import * as React from "react"

import { cn } from "@/lib/utils"

const ToastViewport = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "fixed bottom-4 right-4 z-[100] flex w-[360px] flex-col gap-2",
        className,
      )}
      {...props}
    />
  ),
)
ToastViewport.displayName = "ToastViewport"

interface ToastProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "destructive"
}

const Toast = React.forwardRef<HTMLDivElement, ToastProps>(
  ({ className, variant = "default", ...props }, ref) => (
    <div
      ref={ref}
      role="alert"
      className={cn(
        "pointer-events-auto relative w-full rounded-lg border p-4 text-sm shadow-lg",
        variant === "destructive"
          ? "border-destructive/40 bg-destructive/10 text-destructive"
          : "border-border bg-card text-card-foreground",
        className,
      )}
      {...props}
    />
  ),
)
Toast.displayName = "Toast"

export { Toast, ToastViewport }