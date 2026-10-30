import * as React from 'react';
import { Slot } from 'radix-ui';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/utils';
const buttonVariants = cva('ui-button', {
  variants: {
    variant: {
      default: 'ui-button-default',
      outline: 'ui-button-outline',
    },
    size: { default: 'ui-button-size-default' },
  },
  defaultVariants: { variant: 'default', size: 'default' },
});
// shadcn/ui button pattern; kept in source for local customization.
export function Button({
  className,
  variant,
  size,
  asChild = false,
  type = 'button',
  ...props
}: React.ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : 'button';
  return (
    <Comp
      type={type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}
