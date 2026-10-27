import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-400 disabled:pointer-events-none disabled:opacity-50 select-none",
  {
    variants: {
      variant: {
        default:
          "bg-zinc-50 text-zinc-900 shadow hover:bg-zinc-200 active:bg-zinc-300 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200",
        destructive:
          "bg-red-500/15 text-red-400 border border-red-500/30 hover:bg-red-500/25 active:bg-red-500/30",
        outline:
          "border border-zinc-800 bg-zinc-950/60 text-zinc-200 hover:bg-zinc-900 hover:border-zinc-700 active:bg-zinc-800/80 shadow-sm",
        secondary:
          "bg-zinc-900 text-zinc-200 border border-zinc-800/80 hover:bg-zinc-800 hover:border-zinc-700 active:bg-zinc-700/80",
        ghost:
          "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900/80 active:bg-zinc-800",
        link: "text-cyan-400 underline-offset-4 hover:underline",
        cyan:
          "bg-cyan-500 text-zinc-950 font-semibold hover:bg-cyan-400 shadow-[0_0_20px_rgba(6,182,212,0.25)] active:bg-cyan-600",
        emerald:
          "bg-emerald-500 text-zinc-950 font-semibold hover:bg-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.25)] active:bg-emerald-600",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-11 rounded-md px-6 text-base",
        icon: "h-9 w-9",
        "icon-sm": "h-7 w-7 rounded-md",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

const Button = React.forwardRef(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
