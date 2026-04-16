import { useEffect, useMemo } from 'react';
import { EditorContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { marked } from 'marked';
import TurndownService from 'turndown';

const turndown = new TurndownService({
  headingStyle: 'atx',
  bulletListMarker: '-',
  codeBlockStyle: 'fenced',
});

const markdownToHtml = (markdown) => {
  const parsed = marked.parse(markdown || '', { async: false, gfm: true });
  return typeof parsed === 'string' && parsed.trim() ? parsed : '<p></p>';
};

const valueToEditorHtml = (value) => markdownToHtml(value);

const editorToValue = (editor) =>
  turndown.turndown(editor.getHTML()).replace(/\n{3,}/g, '\n\n').trim();

const IconUndo = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/></svg>;
const IconRedo = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3l3 2.7"/></svg>;
const IconBullet = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>;
const IconOrder = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="10" y1="6" x2="21" y2="6"/><line x1="10" y1="12" x2="21" y2="12"/><line x1="10" y1="18" x2="21" y2="18"/><path d="M4 6h1v4"/><path d="M4 10h2"/><path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1"/></svg>;
const IconCode = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>;
const IconQuote = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z"/><path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z"/></svg>;
const IconRule = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>;

function ToolbarButton({ active = false, disabled = false, onClick, title, children }) {
  return (
    <button
      type="button"
      className={`cv-toolbar-btn ${active ? 'active' : ''}`}
      disabled={disabled}
      onClick={onClick}
      title={title}
    >
      {children}
    </button>
  );
}

export default function CvWysiwygEditor({
  value = '',
  format = 'markdown',
  onChange,
  readOnly = false,
}) {
  const initialContent = useMemo(() => valueToEditorHtml(value), [value]);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3],
        },
      }),
    ],
    content: initialContent,
    editable: !readOnly,
    onUpdate: ({ editor: instance }) => {
      if (!onChange) return;
      onChange(editorToValue(instance));
    },
  });

  useEffect(() => {
    if (!editor) return;
    const nextContent = valueToEditorHtml(value);
    if (editor.isFocused) return;
    if (editor.getHTML() !== nextContent) {
      editor.commands.setContent(nextContent, false);
    }
  }, [editor, value]);

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!readOnly);
  }, [editor, readOnly]);

  if (!editor) {
    return <div className="cv-wysiwyg-loading">Đang mở trình chỉnh sửa...</div>;
  }

  return (
    <div className="cv-wysiwyg">
      <div className="cv-toolbar-wrapper">
        <div className="cv-toolbar-pill">
          {/* History */}
          <ToolbarButton
            title="Undo"
            disabled={readOnly || !editor.can().chain().focus().undo().run()}
            onClick={() => editor.chain().focus().undo().run()}
          >
            <IconUndo />
          </ToolbarButton>
          <ToolbarButton
            title="Redo"
            disabled={readOnly || !editor.can().chain().focus().redo().run()}
            onClick={() => editor.chain().focus().redo().run()}
          >
            <IconRedo />
          </ToolbarButton>

          <div className="cv-toolbar-divider" />

          {/* Text Formatting */}
          <ToolbarButton
            title="Bold"
            active={editor.isActive('bold')}
            disabled={readOnly}
            onClick={() => editor.chain().focus().toggleBold().run()}
          >
            <strong style={{ fontFamily: 'serif', fontSize: '1rem' }}>B</strong>
          </ToolbarButton>
          <ToolbarButton
            title="Italic"
            active={editor.isActive('italic')}
            disabled={readOnly}
            onClick={() => editor.chain().focus().toggleItalic().run()}
          >
            <em style={{ fontFamily: 'serif', fontSize: '1rem' }}>I</em>
          </ToolbarButton>
          <ToolbarButton
            title="Strikethrough"
            active={editor.isActive('strike')}
            disabled={readOnly}
            onClick={() => editor.chain().focus().toggleStrike().run()}
          >
            <span style={{ textDecoration: 'line-through', fontFamily: 'serif' }}>S</span>
          </ToolbarButton>

          <div className="cv-toolbar-divider" />

          {/* Headings */}
          <ToolbarButton
            title="Heading 1"
            active={editor.isActive('heading', { level: 1 })}
            disabled={readOnly}
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
          >
            <span style={{ fontWeight: 800 }}>H1</span>
          </ToolbarButton>
          <ToolbarButton
            title="Heading 2"
            active={editor.isActive('heading', { level: 2 })}
            disabled={readOnly}
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          >
            <span style={{ fontWeight: 700 }}>H2</span>
          </ToolbarButton>

          <div className="cv-toolbar-divider" />

          {/* Blocks */}
          <ToolbarButton
            title="Bullet List"
            active={editor.isActive('bulletList')}
            disabled={readOnly}
            onClick={() => editor.chain().focus().toggleBulletList().run()}
          >
            <IconBullet />
          </ToolbarButton>
          <ToolbarButton
            title="Ordered List"
            active={editor.isActive('orderedList')}
            disabled={readOnly}
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
          >
            <IconOrder />
          </ToolbarButton>
          <ToolbarButton
            title="Blockquote"
            active={editor.isActive('blockquote')}
            disabled={readOnly}
            onClick={() => editor.chain().focus().toggleBlockquote().run()}
          >
            <IconQuote />
          </ToolbarButton>
          <ToolbarButton
            title="Code Block"
            active={editor.isActive('codeBlock')}
            disabled={readOnly}
            onClick={() => editor.chain().focus().toggleCodeBlock().run()}
          >
            <IconCode />
          </ToolbarButton>
          <ToolbarButton
            title="Horizontal Rule"
            disabled={readOnly}
            onClick={() => editor.chain().focus().setHorizontalRule().run()}
          >
            <IconRule />
          </ToolbarButton>
        </div>
      </div>

      <EditorContent editor={editor} className="cv-editor-content" />
    </div>
  );
}
