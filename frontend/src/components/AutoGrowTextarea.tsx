import { useEffect, useRef, type TextareaHTMLAttributes } from "react";

type Props = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  /** Minimum visible rows; the field grows past this as text is added. */
  minRows?: number;
  /** Height at which the field stops growing and starts scrolling. */
  maxHeight?: number;
};

/**
 * Textarea that always shows its full content.
 *
 * Character bios, scene descriptions and dialogue are long-form by nature, so a
 * fixed 88px box hides most of the text. This keeps the box at least `minRows`
 * tall, grows it to fit the content, and only scrolls beyond `maxHeight`.
 */
export function AutoGrowTextarea({ minRows = 3, maxHeight = 480, value, style, ...rest }: Props) {
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    element.style.height = "auto";
    const styles = window.getComputedStyle(element);
    const lineHeight = Number.parseFloat(styles.lineHeight) || 20;
    const padding = Number.parseFloat(styles.paddingTop) + Number.parseFloat(styles.paddingBottom);
    const border = Number.parseFloat(styles.borderTopWidth) + Number.parseFloat(styles.borderBottomWidth);
    const minimum = lineHeight * minRows + (Number.isFinite(padding) ? padding : 0) + (Number.isFinite(border) ? border : 0);
    const target = Math.max(element.scrollHeight, minimum);
    element.style.height = `${Math.min(target, maxHeight)}px`;
    element.style.overflowY = target > maxHeight ? "auto" : "hidden";
  }, [value, minRows, maxHeight]);

  return <textarea ref={ref} rows={minRows} value={value} style={style} {...rest} />;
}
