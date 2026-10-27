import * as React from "react"
import { cva } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-1 focus:ring-zinc-400 font-mono tracking-tight",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-zinc-100 text-zinc-900 shadow hover:bg-zinc-200",
        secondary:
          "border-zinc-800 bg-zinc-900/90 text-zinc-300 hover:bg-zinc-850",
        destructive:
          "border-red-500/30 bg-red-500/10 text-red-400",
        outline: "border-zinc-800 text-zinc-400",
        cyan:
          "border-cyan-500/30 bg-cyan-500/10 text-cyan-400 font-semibold",
        emerald:
          "border-emerald-500/30 bg-emerald-500/10 text-emerald-400 font-semibold",
        amber:
          "border-amber-500/30 bg-amber-500/10 text-amber-400 font-semibold",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({ className, variant, ...props }) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
