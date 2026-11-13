import type { ComponentProps } from 'react';
import { Dialog } from 'radix-ui';
import { cn } from '../../lib/utils';

export const Sheet = Dialog.Root;
export const SheetTitle = Dialog.Title;
export const SheetClose = Dialog.Close;

export function SheetContent({
  className,
  children,
  ...props
}: ComponentProps<typeof Dialog.Content>) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="sheet-overlay" />
      <Dialog.Content className={cn('sheet-content', className)} {...props}>
        {children}
      </Dialog.Content>
    </Dialog.Portal>
  );
}
