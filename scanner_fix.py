            # Save debug image to a file that can be served by the web app
            import os
            debug_filename = f"debug_sheet_{page_num}.png"
            debug_path = os.path.join("static", "debug_images", debug_filename)
            
            # Create debug_images directory if it doesn't exist
            os.makedirs(os.path.dirname(debug_path), exist_ok=True)
            
            # Save the debug image
            cv2.imwrite(debug_path, debug_image)
            
            return {
                'sheet': page_num,
                'student_id': student_id,
                'answers': all_answers,
                'debug_image_url': f"/static/debug_images/{debug_filename}"
            }
            
        except Exception as e:
            logger.error(f"Sheet {page_num}: Error processing image - {e}")
            return {"sheet": page_num, "error": f"Error processing image: {e}"}
