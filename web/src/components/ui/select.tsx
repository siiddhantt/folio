import type { ComponentProps } from 'react';
import { Select as Primitive } from 'radix-ui';
import { Check, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '../../lib/utils';

export const Select = Primitive.Root;
export const SelectValue = Primitive.Value;

export function SelectTrigger({
  className,
  children,
  ...props
}: ComponentProps<typeof Primitive.Trigger>) {
  return (
    <Primitive.Trigger className={cn('select-trigger', className)} {...props}>
      {children}
      <Primitive.Icon asChild>
        <ChevronDown aria-hidden="true" />
      </Primitive.Icon>
    </Primitive.Trigger>
  );
}

export function SelectContent({
  children,
  className,
  ...props
}: ComponentProps<typeof Primitive.Content>) {
  return (
    <Primitive.Portal>
      <Primitive.Content
        className={cn('select-content', className)}
        position="popper"
        sideOffset={4}
        {...props}
      >
        <Primitive.ScrollUpButton className="select-scroll">
          <ChevronUp aria-hidden="true" />
        </Primitive.ScrollUpButton>
        <Primitive.Viewport>{children}</Primitive.Viewport>
        <Primitive.ScrollDownButton className="select-scroll">
          <ChevronDown aria-hidden="true" />
        </Primitive.ScrollDownButton>
      </Primitive.Content>
    </Primitive.Portal>
  );
}

export function SelectItem({
  children,
  className,
  ...props
}: ComponentProps<typeof Primitive.Item>) {
  return (
    <Primitive.Item className={cn('select-item', className)} {...props}>
      <Primitive.ItemText>{children}</Primitive.ItemText>
      <Primitive.ItemIndicator>
        <Check aria-hidden="true" />
      </Primitive.ItemIndicator>
    </Primitive.Item>
  );
}
